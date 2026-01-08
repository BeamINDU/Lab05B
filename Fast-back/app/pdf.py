from fpdf import FPDF
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
from typing import Generic, Self, Concatenate, Iterable, TypeVar
from binascii import Incomplete
import math
from pydantic import BaseModel
from app import schemas, utils
from app.model.model import getRotDim
from app.logger import logger


# settings
fontStyle = "Waree"

min_num_col = 2
min_num_row = 2
max_num_col = 4
max_num_row = 4


### helper functions
def custom_ceil(number, base=1):
    return base * math.ceil(number / base)


# Create a base class that ensures masterid exists
class HasMasterIdModel(BaseModel):
    masterid: str


# Constrain T to be both BaseModel and have masterid
T = TypeVar("T", bound=schemas.SimDetail | schemas.SimBatch)


class GroupedItem(BaseModel, Generic[T]):
    item: T
    qty: int


def groupByMaster(simObjects: list[T]) -> dict[str, GroupedItem[T]]:
    grouped: dict[str, GroupedItem[T]] = {}

    for obj in simObjects:
        master_id = obj.masterid  # Now type-safe!

        if master_id in grouped:
            grouped[master_id].qty += 1
        else:
            grouped[master_id] = GroupedItem(item=obj, qty=1)

    return grouped


def create_color_icon(color: str):
    img = Image.new("RGBA", (500, 100), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((210, 10, 290, 90), fill="#000000")
    draw.rectangle((212, 12, 288, 88), fill=color)
    return img


# Report class creates header and footer for the entire document
class PDF(FPDF):
    subHeader: Callable[Concatenate[Self, ...], None] | None = None
    subHeaderParams: list = []

    def header(self):
        self.set_font(fontStyle, style="B", size=20)
        self.cell(self.epw, 10, "Palletization Report", border=0, align="C")
        self.ln(10)
        if self.subHeader:
            self.subHeader(self, *self.subHeaderParams)

    def footer(self):
        # Position cursor at 1.5 cm from bottom:
        self.set_y(-15)
        self.set_font(fontStyle, style="I", size=8)
        self.cell(0, 10, f"Page {self.page_no()} / {{nb}}", align="C")


# first page subHeader
def simdetails_subHeader(pdf: PDF):
    pdf.set_font(fontStyle, style="B", size=15)
    pdf.cell(pdf.epw, 10, "Simulation Details", border=0, align="C")
    pdf.ln(10)
    pdf.set_font(fontStyle, size=10)


# instruction page subHeader
def batchDetails_subHeader(pdf: PDF, subHeaderData: Iterable[Incomplete]):
    pdf.set_font(fontStyle, style="B", size=15)
    pdf.cell(pdf.epw, 10, "Product Placements", border=0, align="C")
    pdf.ln(10)
    pdf.set_font(fontStyle, size=7)
    with pdf.table(
        subHeaderData, text_align="C", col_widths=(1, 1, 1, 2, 2, 1, 1, 1, 1)
    ):
        pass
    pdf.ln(1)
    pdf.rect(pdf.x, pdf.y, pdf.epw, pdf.eph - pdf.y)


# create a detail table
def detailTable(pdf: PDF, title, groupedList: list[GroupedItem[T]]):
    pdf.set_font(fontStyle, size=10)
    with pdf.table(
        text_align="C", col_widths=(1, 1, 2, 1, 1), num_heading_rows=2
    ) as table:
        table.row([{"text": f"{title}s", "colspan": 5}])
        table.row(
            (f"{title} Code", "Name", "Length x Width x Height", "Quantity", "Color")
        )
        for batch in groupedList:
            table.row(
                (
                    str(batch.item.code),
                    str(batch.item.name),
                    f"{batch.item.length} x {batch.item.width} x {batch.item.height}",
                    str(batch.qty),
                    {"img": create_color_icon(batch.item.color)},
                )
            )


# create report and save in ./pdf/
def create_report(
    simdata: schemas.SimulationGetResponse, simId: str
):  # extract orders, pallets (inside container) and products
    orders: list[schemas.SimOrder] = []
    pallets: list[schemas.SimDetail] = []
    products: list[schemas.SimDetail] = []

    for batch in simdata.data:
        for detail in batch.details:
            if isinstance(detail, schemas.SimDetail):
                orders.extend(detail.orders)
                pallets.append(detail)
                for order in detail.orders:
                    products.extend(order.products)
                continue
            orders.append(detail)
            products.extend(detail.products)

    ordernames = set(order.orders_name for order in orders)

    groupedPallets = groupByMaster(pallets)
    groupedProducts = groupByMaster(products)
    groupedBatches = groupByMaster(simdata.data)

    simType_title = str(
        simdata.simulatetype
        if simdata.simulatetype != "pallet_container"
        else "container"
    ).title()

    simDetailData = (
        (
            "Simulate id",
            "Simulate By",
            "Type",
            "Date",
            "Orders",
            f"{simType_title} Count",
            "Product Count",
        ),
        (
            str(simId),
            str(simdata.simulate_by),
            str(simdata.simulatetype),
            (
                datetime.strptime(simdata.start_datetime, "%Y-%m-%dT%H:%M:%S.%f")
                if isinstance(simdata.start_datetime, str)
                else simdata.start_datetime
            )
            .astimezone(ZoneInfo("Asia/Bangkok"))
            .strftime("%Y/%m/%d %H:%M:%S"),
            "\n".join(sorted(list(ordernames))),
            str(len(simdata.data)),
            str(len(products)),
        ),
    )

    # Instantiation of inherited class
    pdf = PDF()

    # add font
    pdf.add_font(fontStyle, style="", fname="/app/fonts/Waree.ttf", uni=True)
    pdf.add_font(fontStyle, style="B", fname="/app/fonts/Waree-Bold.ttf", uni=True)
    pdf.add_font(fontStyle, style="I", fname="/app/fonts/Waree-Oblique.ttf", uni=True)
    pdf.add_font(
        fontStyle, style="BI", fname="/app/fonts/Waree-BoldOblique.ttf", uni=True
    )

    # first page show overall detail of the simulation
    pdf.subHeader = simdetails_subHeader
    pdf.add_page()
    with pdf.table(simDetailData, text_align="C", col_widths=(1, 1, 1, 2, 2, 1, 1)):
        pass

    # SimBatch table
    pdf.ln(2)
    detailTable(pdf, simType_title, groupedBatches.values())

    # pallet in container table
    if pallets:
        pdf.ln(2)
        detailTable(pdf, "Pallet", groupedPallets.values())

    # product table
    pdf.ln(2)
    detailTable(pdf, "Product", groupedProducts.values())

    # instruction page show step by step instructions
    for batch in simdata.data:
        batchType_title = str(batch.batchtype).title()
        colorImage = create_color_icon(batch.color)
        subHeaderData = (
            (
                "Batch Id",
                f"{batchType_title} Code",
                f"{batchType_title} Name",
                "Length x Width x Height",
                "Load Length x Width x Height",
                "Load Weight",
                "Color",
                "Total Weight%",
                "Total Capacity%",
            ),
            (
                str(batch.batchid),
                str(batch.code),
                str(batch.name),
                f"{batch.length} x {batch.width} x {batch.height}",
                f"{batch.load_length} x {batch.load_width} x {batch.load_height}",
                str(batch.load_weight),
                {"img": colorImage},
                f"{(batch.total_weight / batch.load_weight * 100):.2f}%",
                f"{(batch.total_volume / (batch.load_length * batch.load_width * batch.load_height) * 100):.2f}%",
            ),
        )

        pdf.subHeader = batchDetails_subHeader
        pdf.subHeaderParams = [subHeaderData]
        pdf.add_page()

        # get product out of orders or its simbatch
        batchObjects = [
            object
            for detail in batch.details
            for object in (
                detail.products if isinstance(detail, schemas.SimOrder) else [detail]
            )
        ]
        num_col = min_num_col if len(batchObjects) <= 40 else max_num_col
        num_row = min_num_row if len(batchObjects) <= 40 else max_num_col

        if batch.batchtype == "pallet":
            batchObjects.sort(key=utils.pallet_sort)
        else:
            batchObjects.sort(key=lambda x: utils.container_sort(x, batch.door_position))
            batchObjects = utils.sort_dependencies(batchObjects, utils.supported_corner)

        # calculate remaining space after header
        content_y = pdf.y
        content_x = pdf.x

        content_h = pdf.eph - content_y
        content_w = pdf.epw

        cell_h = content_h / num_row
        cell_w = content_w / num_col

        renderer: utils.IsometricRenderer

        imageResolution = int(1600 / max(num_col, num_row))

        if batch.batchtype == "pallet":
            totalsize = (
                max(batch.load_width, batch.width),
                max(batch.load_length, batch.length),
                batch.height + batch.load_height,
            )
            renderer = utils.IsometricRenderer(
                imageResolution, imageResolution, *totalsize, 0.7
            )
            renderer.addObject(
                schemas.drawObj(
                    **batch.model_dump(),
                    mastertype="pallet",
                    x=0,
                    y=0,
                    z=-batch.height,
                )
            )
        else:
            totalsize = (
                (batch.load_width, batch.load_length, batch.load_height)
                if batch.door_position == "front" or batch.door_position == "top"
                else (batch.load_length, batch.load_width, batch.load_height)
            )
            renderer = utils.IsometricRenderer(
                imageResolution, imageResolution, *totalsize, 0.7
            )
            renderer.addObject(
                schemas.drawObj(
                    **batch.model_dump(exclude={"load_length", "load_width", "load_height"}),
                    mastertype="container",
                    load_length=totalsize[1],
                    load_width=totalsize[0],
                    load_height=totalsize[2],
                    x=0,
                    y=0,
                    z=0,
                )
            )

        for index, batchObject in enumerate(batchObjects):
            if index and not index % (num_col * num_row):
                pdf.add_page()

            pdf.set_font(fontStyle, size=7)
            start_x = content_x + cell_w * (index % num_col)
            start_y = content_y + cell_h * (int(index / num_col) % num_row)
            pdf.rect(start_x, start_y, cell_w, cell_h)
            pdf.set_y(start_y)
            pdf.set_x(start_x)
            masterType = batchObject.mastertype
            objectTitle = (
                str(masterType).title() if masterType != "sim_batch" else "Pallet"
            )
            tableData = (
                (
                    # "Step",
                    f"{objectTitle} Code",
                    f"{objectTitle} Name",
                    # "Length x Width x Height",
                ),
                (
                    # str(index + 1),
                    str(batchObject.code),
                    str(batchObject.name),
                    # f'{batchObject["length"]} x {batchObject["width"]} x {batchObject["height"]}',
                ),
            )
            with pdf.table(
                tableData,
                text_align="C",
                align="L",
                width=cell_w,
                col_widths=(1, 2),
            ):
                pass

            image_start_y = pdf.y

            image_h = cell_h + start_y - image_start_y

            image_size = min(cell_w, image_h)

            rotatedSize = getRotDim(
                batchObject.width,
                batchObject.length,
                batchObject.height,
                batchObject.rotation,
            )

            if masterType == "sim_batch":
                renderer.addObject(
                    schemas.drawObj(
                        **batchObject.model_dump(exclude={"x", "y", "z"}),
                        x=batchObject.x,
                        y=batchObject.y,
                        z=batchObject.z,
                    )
                )
                for order in batchObject.orders:
                    for product in order.products:
                        x, y, z, rot = utils.apply_container_transform(
                            batchObject, product
                        )

                        renderer.addObject(
                            schemas.drawObj(
                                **product.model_dump(
                                    exclude={"x", "y", "z", "rotation"}
                                ),
                                x=x + batchObject.x,
                                y=y + batchObject.y,
                                z=z + batchObject.z + rotatedSize[2],
                                rotation=rot,
                            )
                        )
            else:
                renderer.addObject(
                    schemas.drawObj(
                        **batchObject.model_dump(exclude={"x", "y", "z"}),
                        x=batchObject.x,
                        y=batchObject.y,
                        z=batchObject.z,
                    )
                )

            # Converting Figure to an image:
            renderer.render_scene()
            pdf.image(
                renderer.image,
                start_x + (cell_w - image_size) / 2,
                image_start_y + (image_h - image_size) / 2,
                image_size,
                image_size,
            )

            pdf.set_x(start_x + 2)
            pdf.set_font(fontStyle, size=14)
            pdf.cell(cell_w - 4, 9, str(index + 1), align="L")

    pdf.output(f"/pdf/{simId}.pdf")
