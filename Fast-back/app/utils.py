import itertools
import math
from PIL import Image, ImageDraw, ImageColor
from typing import Literal, Optional, TypedDict
from app import schemas, route_opt_schemas
import distinctipy
import webcolors
from datetime import datetime
from fastapi import HTTPException
from app.model import model
from app.logger import logger


def apply_container_transform(
    container: schemas.drawObj, item: schemas.drawObj
) -> tuple[float, float, float, int]:
    """
    Apply container's rotation to item's position and rotation.

    Args:
        container: The container with rotation
        item: The item to transform (with position relative to container)

    Returns:
        Tuple of (new_x, new_y, new_z, new_rotation)
    """
    container_rotation = container.rotation or 0
    item_rotation = item.rotation or 0

    # Compose rotations
    if 0 <= container_rotation < len(
        model.ROTATION_PATTERNS
    ) and 0 <= item_rotation < len(model.ROTATION_PATTERNS):
        container_pattern = model.ROTATION_PATTERNS[container_rotation]
        item_pattern = model.ROTATION_PATTERNS[item_rotation]
        composed = tuple(item_pattern[container_pattern[i]] for i in range(3))
        try:
            new_rotation = model.ROTATION_PATTERNS.index(composed)
        except ValueError:
            new_rotation = item_rotation
    else:
        new_rotation = item_rotation

    # Get container's rotated dimensions
    cont_base_dims = [container.load_width, container.load_length, container.load_height]
    cont_pattern = (
        model.ROTATION_PATTERNS[container_rotation]
        if 0 <= container_rotation < len(model.ROTATION_PATTERNS)
        else (0, 1, 2)
    )
    cont_dims = [cont_base_dims[cont_pattern[i]] for i in range(3)]

    # Get container's rotated dimensions
    item_dims = [item.width, item.length, item.height]

    # Position transformation patterns: (axis_mapping, [flip_flags])
    # Each entry: which source axis maps to each dest axis, and whether to flip (dimension - value)
    POSITION_TRANSFORMS = (
        ((0, 1, 2), (False, False, False)),  # 0: no rotation
        ((1, 0, 2), (False, True, False)),  # 1: rotate Z -90°
        ((2, 1, 0), (True, False, False)),  # 2: rotate Y 90°
        ((1, 2, 0), (False, False, False)),  # 3: rotate X 90°, Z -90°
        ((0, 2, 1), (False, True, False)),  # 4: rotate X 90°
        ((2, 0, 1), (True, True, False)),  # 5: rotate X 90°, Y 90°
    )

    position = [item.x, item.y, item.z]
    transform = (
        POSITION_TRANSFORMS[container_rotation]
        if 0 <= container_rotation < len(POSITION_TRANSFORMS)
        else POSITION_TRANSFORMS[0]
    )
    axis_map, flips = transform

    new_position = []
    for i in range(3):
        source_axis = axis_map[i]
        value = position[source_axis]
        if flips[i]:
            value = (
                cont_dims[i]
                - value
                - item_dims[model.ROTATION_PATTERNS[new_rotation][i]]
            )
        new_position.append(value)

    return new_position[0], new_position[1], new_position[2], new_rotation


def supported_corner(item1: schemas.SimDetail, item2: schemas.SimDetail) -> int:
    # if item1.x is not None or item2.x is not None:
    #     return False
    x1, y1, z1 = item1.x, item1.y, item1.z
    # supported by the ground
    if z1 == 0:
        return False
    w1, l1, _ = model.getRotDim(item1.width, item1.length, item1.height, item1.rotation)
    x2, y2, z2 = item2.x, item2.y, item2.z
    w2, l2, h2 = model.getRotDim(
        item2.width, item2.length, item2.height, item2.rotation
    )

    # item2 is not directly underneath
    if z1 != z2 + h2:
        return False

    return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + l1 <= y2 or y2 + l2 <= y1)

    # bottom_corners = [
    #     (x1, y1),
    #     (x1 + w1, y1),
    #     (x1, y1 + l1),
    #     (x1 + w1, y1 + l1),
    # ]
    # for corner in bottom_corners:
    #     if x2 <= corner[0] < x2 + w2 and y2 <= corner[1] < y2 + l2:
    #         return True
    # return False


def sort_dependencies(
    items: list[schemas.SimDetail], supported_func
) -> list[schemas.SimDetail]:
    temp = items.copy()
    newSorted = []
    while len(temp):
        item = temp.pop(0)
        independent = True
        for i, item2 in enumerate(temp):
            if item != item2 and supported_func(item, item2):
                # print(f"{item.batchdetailid}, {item2.batchdetailid}")
                temp.insert(i + 1, item)
                independent = False
                break
        if independent:
            newSorted.append(item)
    return newSorted


# sort so that each boxes does not cover the other boxes
def pallet_sort(item: schemas.SimDetail):
    """sort items in pallet"""
    x, y, z = item.x, item.y, item.z
    w, l, h = model.getRotDim(item.width, item.length, item.height, item.rotation)
    return z + h, x, y, w, l


def container_sort(
    item: schemas.SimDetail, door_position: Literal["front", "side"] = "front"
):
    """sort items in container"""
    x, y, z = item.x, item.y, item.z
    w, l, h = model.getRotDim(item.width, item.length, item.height, item.rotation)
    loadHeight = item.load_height if item.mastertype == "sim_batch" else 0
    # if door_position == "side":
    #     return x, z, y, w, h + loadHeight, l
    # else:
    return y, z, x, l, h + loadHeight, w


def new_color(excludes: list[str] = []) -> str:
    excludes_rgb = [
        tuple(x / 255 for x in webcolors.hex_to_rgb(color)) for color in excludes
    ]
    colors = distinctipy.get_colors(1, excludes_rgb)
    return webcolors.rgb_to_hex(tuple(int(x * 255) for x in colors[0]))

def convert_route_door_position(door_position: str):
    match door_position:
        case "side-right":
            return "right"
        case "side-left":
            return "left"
        case _:
            return door_position


def route_opt_to_SimulationRequest(
    payload: route_opt_schemas.LogisticsRequest,
) -> tuple[
    dict[int, schemas.SimulationRequest],
    dict[int, route_opt_schemas.JobSelectionDetailRequest],
    dict[int, route_opt_schemas.VehicleBase],
    dict[int, list[route_opt_schemas.VehicleBase]],
    dict[int, route_opt_schemas.PackageDetail],
    dict[int, route_opt_schemas.ProductRequest],
]:

    requests: dict[int, schemas.SimulationRequest] = {}

    jobById: dict[int, route_opt_schemas.JobSelectionDetailRequest] = {}

    vehicleById: dict[int, route_opt_schemas.VehicleBase] = {}

    jobVehicles: dict[int, list[route_opt_schemas.VehicleBase]] = {}

    packageById: dict[int, route_opt_schemas.PackageDetail] = {}

    productByNo: dict[int, route_opt_schemas.ProductRequest] = {}

    for job in payload.job_selection_detail:
        orders = []
        # orderids = []
        num_products = 0
        for detail in job.job_detail:
            for order in detail.orders:
                # orders_id = None
                # try:
                #     orders_id = orderids.index(order.order_no)
                # except:
                #     orders_id = len(orderids)
                #     orderids.append(order.order_no)

                req_order = schemas.OrderRead(
                    orders_id=order.orders_id,
                    orders_number=order.orders_no,
                    orders_name=order.orders_no,
                    created_by="route_opt",
                    deliveryby="route_opt",
                    plan_send_date=datetime.now(),
                    products=[],
                )
                for product in order.products:
                    num_products += product.quantity

                    req_order.products.append(
                        schemas.OrderListCreate(
                            product_id=product.product_id,
                            product_code=product.product_no,
                            product_name=product.product_name,
                            product_width=product.w_mm,
                            product_length=product.l_mm,
                            product_height=product.h_mm,
                            product_weight=product.weight,
                            pickup_priority=detail.seq,
                            max_stack=product.stack_limit if product.stack_limit else -1,
                            is_stack=product.is_do_not_stack,
                            is_side_up=product.is_side_up,
                            qty=product.quantity,
                        )
                    )
                    productByNo[product.product_no] = product
                orders.append(req_order)

        containers = []
        containers.append(
            schemas.PackageAvaliable(
                package_id=job.vehicle_id,
                package_code=str(job.vehicle_id),
                package_name=job.vehicle_name,
                package_length=job.container_length,
                package_width=job.container_width,
                package_height=job.container_height,
                package_weight=job.container_weight,
                load_length=job.load_length,
                load_width=job.load_width,
                load_height=job.load_height,
                load_weight=job.load_weight,
                available_qty=1,
                created_by="route_opt",
                door_position=convert_route_door_position(job.door_position),
            )
        )
        vehicleById[job.vehicle_id] = job
        jobVehicles[job.job_id] = [job]
        if job.trailer_vehicle:
            containers.append(
                schemas.PackageAvaliable(
                    package_id=job.trailer_vehicle.vehicle_id,
                    package_code=str(job.trailer_vehicle.vehicle_id),
                    package_name=job.trailer_vehicle.vehicle_name,
                    package_length=job.trailer_vehicle.container_length,
                    package_width=job.trailer_vehicle.container_width,
                    package_height=job.trailer_vehicle.container_height,
                    package_weight=job.trailer_vehicle.container_weight,
                    load_length=job.trailer_vehicle.load_length,
                    load_width=job.trailer_vehicle.load_width,
                    load_height=job.trailer_vehicle.load_height,
                    load_weight=job.trailer_vehicle.load_weight,
                    available_qty=1,
                    created_by="route_opt",
                    door_position=convert_route_door_position(job.door_position),
                )
            )
            vehicleById[job.trailer_vehicle.vehicle_id] = job.trailer_vehicle
            jobVehicles[job.job_id].append(job.trailer_vehicle)

        for package in payload.package.package_detail:
            packageById[package.package_id] = package

        pallets = (
            [
                schemas.PalletAvaliable(
                    palletid=pallet.package_id,
                    palletcode=pallet.package_code,
                    palletname=pallet.package_name,
                    palletlength=pallet.package_length,
                    palletwidth=pallet.package_width,
                    palletheight=pallet.package_height,
                    palletweight=pallet.package_weight,
                    load_length=pallet.load_length,
                    load_width=pallet.load_width,
                    load_height=pallet.load_height,
                    load_weight=pallet.load_weight,
                    created_by="route_opt",
                    available_qty=num_products,
                )
                for pallet in payload.package.package_detail
            ]
            if payload.package.package_type == "pallet"
            else []
        )

        request = schemas.SimulationRequest(
            orders=orders,
            containers=containers,
            pallets=pallets,
            simulatetype="pallet_container" if pallets else "container",
        )
        requests[job.job_id] = request
        jobById[job.job_id] = job
    return requests, jobById, vehicleById, jobVehicles, packageById, productByNo


def simOrder_to_route(
    order: schemas.SimOrder,
    to_add: list[route_opt_schemas.OrderResponse],
    productByNo: dict[int, route_opt_schemas.ProductRequest],
):
    orderRes = route_opt_schemas.OrderResponse(
        orders_id=order.orders_id,
        orders_no=order.orders_number,
        products=[],
    )
    totalWeight: float = 0
    totalCap: float = 0
    for idx, product in enumerate(order.products):
        productReq = productByNo.get(product.code)
        if not productReq:
            continue
        orientation = model.getOrien(product.rotation)
        rotDim = model.getRotDim(
            productReq.w_mm,
            productReq.l_mm,
            productReq.h_mm,
            product.rotation,
        )
        productRes = route_opt_schemas.ProductResponse(
            **productReq.model_dump(exclude={"w_mm", "l_mm", "h_mm"}),
            item_no=idx + 1,
            position=route_opt_schemas.Position(
                x=product.x,
                y=product.y,
                z=product.z,
            ),
            orientation=route_opt_schemas.Orientation(
                x=orientation[0],
                y=orientation[1],
                z=orientation[2],
            ),
            w_mm=rotDim[0],
            l_mm=rotDim[1],
            h_mm=rotDim[2],
        )

        totalWeight += productReq.weight
        totalCap += productReq.l_mm * productReq.w_mm * productReq.h_mm

        orderRes.products.append(productRes)

    to_add.append(orderRes)
    return totalWeight, totalCap


class reformated_snapshot(TypedDict):
    orders: dict[str, schemas.OrderRead]
    products: dict[str, schemas.ModelProduct]
    pallets: Optional[dict[str, schemas.ModelPallet]]
    containers: Optional[dict[str, schemas.ModelContainer]]


def reformatSnapshotData(
    snapshot_data: schemas.SimulationPayload | None,
) -> reformated_snapshot | None:
    if not snapshot_data:
        return None

    reformated: reformated_snapshot = {
        "orders": {},
        "products": {},
        "pallets": {},
        "containers": {},
    }
    if snapshot_data.orders:
        for order in snapshot_data.orders:
            reformated["orders"][str(order.orders_id)] = order

    if snapshot_data.products:
        for product in snapshot_data.products:
            reformated["products"][str(product.product_id)] = product

    if snapshot_data.pallets:
        for pallet in snapshot_data.pallets:
            reformated["pallets"][str(pallet.palletid)] = pallet

    if snapshot_data.containers:
        for container in snapshot_data.containers:
            reformated["containers"][str(container.package_id)] = container

    return reformated


def convert_modelpallet(
    pallets: list[schemas.PalletAvaliable],
) -> list[schemas.ModelPallet]:
    return [
        schemas.ModelPallet.model_validate(
            {
                **pallet.model_dump(),
                "qty": (
                    pallet.qty if pallet.available_qty is None else pallet.available_qty
                ),
            }
        )
        for pallet in pallets
    ]


def convert_modelcontainer(
    containers: list[schemas.PackageAvaliable],
) -> list[schemas.ModelContainer]:
    return [
        schemas.ModelContainer.model_validate(
            {
                **container.model_dump(),
                "qty": (
                    container.qty
                    if container.available_qty is None
                    else container.available_qty
                ),
            }
        )
        for container in containers
    ]


def convert_modelproduct(
    orders: list[schemas.OrderRead],
) -> list[schemas.ModelProduct]:
    return [
        schemas.ModelProduct.model_validate(
            {
                **item.model_dump(),
                "orders_id": order.orders_id,
                "plan_send_date": order.plan_send_date.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
        for order in orders
        for item in order.products
    ]


# simulation functions


def checkItemDim(
    items: list[model.Item],
    containers: list[model.Container],
    packageType: str = "pallets",
):
    maxItemdim = max(
        dim
        for item in items
        for dim in [
            item.length,
            item.width,
            item.height,
        ]
    )
    maxContainerdim = max(
        dim
        for container in containers
        for dim in [container.length, container.width, container.height]
    )

    itemsVolumeSorted = sorted(items, key=lambda x: x.volume)
    containersVolumeSorted = sorted(containers, key=lambda x: x.volume)

    if (
        containersVolumeSorted[-1].volume < itemsVolumeSorted[-1].volume
        or maxItemdim > maxContainerdim
    ):
        raise HTTPException(
            status_code=500,
            detail=f"Unable to arrange items on {packageType} because some items are larger than the {packageType}.",
        )

    itemsWeightSorted = sorted(items, key=lambda x: x.weight)
    containersWeightSorted = sorted(containers, key=lambda x: x.max_weight)
    if containersWeightSorted[-1].max_weight < itemsWeightSorted[-1].weight:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to arrange items on {packageType} because some items are heavier than the {packageType}.",
        )

    return


def simulate_pallets(
    products: list[schemas.ModelProduct],
    pallets: list[schemas.ModelPallet],
) -> list[schemas.SimbatchBase]:
    try:
        # convert request params into model classes
        model_items = model.prepare_products(products)
        model_containers = model.prepare_pallets(pallets)

        model_items.sort(key=lambda x: x.volume)
        model_containers.sort(key=lambda x: x.volume)

        checkItemDim(model_items, model_containers, "pallets")

        solution = model.simulate(model_items, model_containers, centered=True)

        if len(solution["unused"]) > 0:
            raise HTTPException(
                status_code=500,
                detail="Unable to arrange items on pallets because there are insufficient pallets.",
            )

        simulation_result: list[schemas.SimbatchBase] = []

        for container in solution["containers"]:
            batch = schemas.SimbatchBase(
                batchtype="pallet",
                batchmasterid=container.type_id,
                total_weight=container.total_weight,
                details=[],
            )

            for item in container.items:
                batch.details.append(
                    schemas.SimbatchdetailBase(
                        masterid=item.itemType_id,
                        mastertype=item.itemType,
                        orders_id=item.order_id,
                        x=item.position[0],
                        y=item.position[1],
                        z=item.position[2],
                        rotation=item.rotation,
                    )
                )

            simulation_result.append(batch)

        return simulation_result

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def simulate_containers(
    products: list[schemas.ModelProduct],
    containers: list[schemas.ModelContainer],
) -> list[schemas.SimbatchBase]:
    try:
        # convert request params into model classes
        model_items = model.prepare_products(products)
        model_containers = model.prepare_containers(containers)

        model_items.sort(key=lambda x: x.volume)
        model_containers.sort(key=lambda x: x.volume)

        checkItemDim(model_items, model_containers, "containers")

        solution = model.simulate(model_items, model_containers, centered=False)

        if len(solution["unused"]) > 0:
            raise HTTPException(
                status_code=500,
                detail="Unable to arrange items on containers because there are insufficient containers.",
            )

        simulation_result: list[schemas.SimbatchBase] = []

        ## will use parallel processing later...
        for container in solution["containers"]:

            ## Add by Oat

            # print('total items:', len(container.items))

            # ga = SingleContainerGA(container=container)
            # res = ga.run()

            # final_container = res["container"]

            # print('total items after rearranging:', len(container.items))

            batch = schemas.SimbatchBase(
                batchtype="container",
                batchmasterid=container.type_id,
                total_weight=container.total_weight,
                details=[],
            )

            for item in container.items:
                batch.details.append(
                    schemas.SimbatchdetailBase(
                        masterid=item.itemType_id,
                        mastertype=item.itemType,
                        orders_id=item.order_id,
                        x=item.position[0],
                        y=item.position[1],
                        z=item.position[2],
                        rotation=item.rotation,
                    )
                )

            simulation_result.append(batch)

        return simulation_result

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def simulate_pallet_containers(
    products: list[schemas.ModelProduct],
    pallets: list[schemas.ModelPallet],
    containers: list[schemas.ModelContainer],
) -> list[schemas.SimbatchBase]:
    try:
        # convert request params into model classes
        model_products = model.prepare_products(products)
        model_pallets = model.prepare_pallets(pallets)

        model_products.sort(key=lambda x: x.volume)
        model_pallets.sort(key=lambda x: x.volume)

        checkItemDim(model_products, model_pallets, "pallets")

        logger.info("start pallet simulate")
        pallet_solution = model.simulate(model_products, model_pallets, centered=True)
        logger.info("completed pallet simulate")

        if len(pallet_solution["unused"]) > 0:
            raise HTTPException(
                status_code=500,
                detail="Unable to arrange items on pallets because there are insufficient pallets.",
            )

        print("finished sorting items to each pallet")

        model_items = model.prepare_palletitems(pallet_solution["containers"])
        model_containers = model.prepare_containers(containers)

        model_items.sort(key=lambda x: x.volume)
        model_containers.sort(key=lambda x: x.volume)

        checkItemDim(model_items, model_containers, "containers")

        logger.info("start container simulate")
        solution = model.simulate(model_items, model_containers, centered=True)
        logger.info("completed container simulate")

        if len(solution["unused"]) > 0:
            raise HTTPException(
                status_code=500,
                detail="Unable to arrange items on containers because there are insufficient containers.",
            )

        print("finished sorting pallet in container")

        simulation_result: list[schemas.SimbatchBase] = []

        for pallet_idx, pallet in enumerate(pallet_solution["containers"]):

            batch = schemas.SimbatchBase(
                batchtype="palletoncontainer",
                batchid=pallet_idx,  # Use enumerate index for consistent batch IDs
                batchmasterid=pallet.type_id,
                total_weight=pallet.total_weight,
                details=[],
            )
            for item in pallet.items:
                batch.details.append(
                    schemas.SimbatchdetailBase(
                        masterid=item.itemType_id,
                        mastertype=item.itemType,
                        orders_id=item.order_id,
                        x=item.position[0],
                        y=item.position[1],
                        z=item.position[2],
                        rotation=item.rotation,
                    )
                )
            simulation_result.append(batch)

        # Assign unique batch IDs to containers, starting after pallet IDs
        num_pallets = len(pallet_solution["containers"])

        for container_idx, container in enumerate(solution["containers"]):

            batch = schemas.SimbatchBase(
                batchtype="container",
                batchid=num_pallets + container_idx,  # Unique ID after pallet IDs
                batchmasterid=container.type_id,
                total_weight=container.total_weight,
                details=[],
            )
            for item in container.items:
                batch.details.append(
                    schemas.SimbatchdetailBase(
                        mastertype="sim_batch",
                        masterid=item.pallet_id,  # Use pallet_id to reference the original pallet batch
                        orders_id=None,
                        x=item.position[0],
                        y=item.position[1],
                        z=item.position[2],
                        rotation=item.rotation,
                    )
                )
            simulation_result.append(batch)

        print("finished all steps in simulate_pallet_containers")

        return simulation_result

    except HTTPException as e:
        raise e
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


def simulate(payload: schemas.SimulationPayload, simulatetype: str):
    # logger.info(payload.model_dump_json())
    totalproductQty = sum(product.qty for product in payload.products)

    if payload.containers:
        for container in payload.containers:
            container.qty = min(container.qty, totalproductQty)
    if payload.pallets:
        for pallet in payload.pallets:
            pallet.qty = min(pallet.qty, totalproductQty)

    simulation_result = None
    match simulatetype:
        case "pallet":
            simulation_result = simulate_pallets(payload.products, payload.pallets)
        case "container":
            simulation_result = simulate_containers(
                payload.products, payload.containers
            )
        case "pallet_container":
            simulation_result = simulate_pallet_containers(
                payload.products, payload.pallets, payload.containers
            )
        case _:
            raise HTTPException(status_code=400, detail="simulation type not found.")

    if not simulation_result:
        raise HTTPException(status_code=500, detail=f"simulation no results.")

    # logger.info(f"results: {[result.model_dump() for result in simulation_result]}")
    return simulation_result


class IsometricRenderer:

    # 0-3: vertices and 4: dim value
    PALLET_PATTERNS = (
        # Top faces (3 segments)
        (2, 5, 41, 38, 1.3),  # Top segment 1
        (5, 41, 44, 8, 1.3),  # Top segment 2
        (44, 8, 11, 47, 1.3),  # Top segment 3
        # Right face (top part)
        (47, 11, 10, 46, 0.8),  # Right face
        # Right faces (3 segments)
        (10, 22, 21, 9, 0.8),  # Right segment 1
        (22, 21, 33, 34, 0.8),  # Right segment 2
        (33, 34, 46, 45, 0.8),  # Right segment 3
        # Front faces (3 segments)
        (38, 37, 40, 41, 1),  # Front segment 1
        (40, 41, 44, 43, 1),  # Front segment 2
        (44, 43, 46, 47, 1),  # Front segment 3
        # Front face (bottom part)
        (36, 37, 46, 45, 1),  # Front face
    )
    CUBE_PATTERNS = (
        (47, 38, 36, 45, 1),  # Front face
        (47, 11, 9, 45, 0.8),  # Right face
        (47, 38, 2, 11, 1.3),  # Top face
    )

    CONTAINER_PATTERNS = (
        (0, 2, 11, 9, 1),  # Back face
        (0, 2, 38, 36, 1),  # Left face
        (0, 9, 45, 36, 0.9),  # Bottom face
    )

    offset_x = 0
    offset_y = 0
    scale_x = 1
    scale_y = 1

    def __init__(
        self,
        screenwidth=800,
        screenheight=800,
        width=800,
        length=800,
        height=800,
        scale=1,
    ):
        """
        Initialize the isometric renderer.

        Args:
            width: Canvas width in pixels
            height: Canvas height in pixels
            scale: Scale factor for converting units to pixels
        """

        minx, _ = self.spaceToScreen(width, 0, 0)
        maxx, _ = self.spaceToScreen(0, length, 0)

        _, miny = self.spaceToScreen(0, 0, height)
        _, maxy = self.spaceToScreen(width, length, 0)

        # # isometric width and height of the container on the image
        package_width = maxx - minx
        package_height = maxy - miny

        self.scale_x = scale * screenwidth / max(package_width, package_height)
        self.scale_y = scale * screenheight / max(package_width, package_height)

        self.offset_x = int(
            math.floor((screenwidth / self.scale_x - maxx - minx) / 2 * self.scale_x)
        )
        self.offset_y = int(
            math.floor((screenheight / self.scale_x - maxy - miny) / 2 * self.scale_y)
        )

        self.image = Image.new("RGBA", (screenwidth, screenheight), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.image)
        self.objects: list[schemas.drawObj] = []

    def spaceToIso(self, x, y, z):
        """
        Convert 3D space coordinates to flattened 2D isometric coordinates.
        x and y coordinates are oblique axes separated by 120 degrees.
        h,v are the horizontal and vertical distances from the origin.
        """
        z = z or 0

        isox = x - z
        isoy = y - z

        return (
            isox,
            isoy,
            (isox - isoy) * math.sqrt(3) / 2,  # Math.cos(Math.PI/6)
            (isox + isoy) / 2,  # Math.sin(Math.PI/6)
        )

    def isoToScreen(self, h, v):
        """
        Convert the given 2D isometric coordinates to 2D screen coordinates.

        h,v are the horizontal and vertical distances from the origin.
        """
        return (
            h * self.scale_x + self.offset_x,
            v * self.scale_y + self.offset_y,
        )

    def spaceToScreen(self, x, y, z):
        """Convert the given 3D space coordinates to 2D screen coordinates."""
        _, _, h, v = self.spaceToIso(x, y, z)
        return self.isoToScreen(h, v)

    def getIsoBounds(self, block: schemas.drawObj):
        x, y, z = block.x, block.y, block.z
        w, l, h = model.getRotDim(
            block.width, block.length, block.height, block.rotation
        )

        frontDown = self.spaceToIso(x + w, y + l, z)
        backUp = self.spaceToIso(x, y, z + h)
        leftDown = self.spaceToIso(x + w, y, z)
        rightDown = self.spaceToIso(x, y + l, z)

        xmin = backUp[0]
        xmax = frontDown[0]
        ymin = backUp[1]
        ymax = frontDown[1]
        hmin = rightDown[2]
        hmax = leftDown[2]
        # print(xmin, xmax, ymin, ymax, hmin, hmax)
        return xmin, xmax, ymin, ymax, hmin, hmax

    def getBounds(self, block: schemas.drawObj):
        x, y, z = block.x, block.y, block.z
        w, l, h = model.getRotDim(
            block.width, block.length, block.height, block.rotation
        )

        return x, x + w, y, y + l, z, z + h

    def areRangesDisjoint(self, amin, amax, bmin, bmax):
        return amax <= bmin or bmax <= amin

    def getIsoSepAxis(self, block_a: schemas.drawObj, block_b: schemas.drawObj):
        a = self.getIsoBounds(block_a)
        b = self.getIsoBounds(block_b)

        sepAxis: Literal["x", "y", "z"] = None
        if self.areRangesDisjoint(a[0], a[1], b[0], b[1]):
            sepAxis = "x"

        if self.areRangesDisjoint(a[2], a[3], b[2], b[3]):
            sepAxis = "y"

        if self.areRangesDisjoint(a[4], a[5], b[4], b[5]):
            sepAxis = "h"
        return sepAxis

    def getSpaceSepAxis(self, block_a: schemas.drawObj, block_b: schemas.drawObj):
        a = self.getBounds(block_a)
        b = self.getBounds(block_b)

        sepAxis: Literal["x", "y", "z"] = None
        if self.areRangesDisjoint(a[0], a[1], b[0], b[1]):
            sepAxis = "x"

        if self.areRangesDisjoint(a[2], a[3], b[2], b[3]):
            sepAxis = "y"

        if self.areRangesDisjoint(a[4], a[5], b[4], b[5]):
            sepAxis = "z"
        return sepAxis

    def getFrontBlock(self, block_a: schemas.drawObj, block_b: schemas.drawObj):
        # If no isometric separation axis is found,
        # then the two blocks do not overlap on the screen.
        # This means there is no "front" block to identify.
        if self.getIsoSepAxis(block_a, block_b):
            return None

        # Find a 3D separation axis, and use it to determine
        # which block is in front of the other.
        a = self.getBounds(block_a)
        b = self.getBounds(block_b)

        axis = self.getSpaceSepAxis(block_a, block_b)

        # print(block_a.color, block_b.color, axis)

        if axis == "x":
            return block_a if a[0] > b[0] else block_b
        elif axis == "y":
            return block_a if a[2] > b[2] else block_b
        elif axis == "z":
            return block_a if a[4] > b[4] else block_b
        else:
            logger.error(f"""found intersecting blocks: 
                         {block_a.model_dump_json()}
                         {block_b.model_dump_json()}""")
            return block_a
            # raise Exception("blocks must be non-intersecting")

    def insertSorted(self, new_obj: schemas.drawObj):
        """Insert a new object into the sorted list maintaining topological order."""
        # Find the correct position based on mastertype ordering first
        new_order = self.masterOrder[new_obj.mastertype]

        new_index = 0

        for i, existing_obj in enumerate(self.objects):
            existing_order = self.masterOrder[existing_obj.mastertype]
            new_index = i
            # skip order that should always be drawn before
            if existing_order < new_order:
                # new index needs to be after something behind it
                new_index += 1
                continue
            # stop before order that should always be drawn after
            if existing_order > new_order:
                break
            front_block = self.getFrontBlock(new_obj, existing_obj)
            if front_block:
                if front_block == new_obj:
                    # if the new object is infront
                    # new index needs to be after something behind it
                    new_index += 1
                else:
                    # if the new object is behind
                    new_obj.clipping.append(existing_obj)
        # print(new_index)
        self.objects.insert(new_index, new_obj)

    def addObject(self, obj: schemas.drawObj):
        if obj.mastertype != "product" and (
            obj.load_length is None or obj.load_width is None or obj.load_height is None
        ):
            raise Exception(f"{obj.mastertype} has no loadsize.")
        # print("inserting", obj.color)
        self.insertSorted(obj)

    def getProjected(self, x, y, z, w, l, h):
        # Pre-calculate coordinate arrays
        x_coords = [x, x + w / 3, x + w * 2 / 3, x + w]
        y_coords = [z, z + l / 3, z + l * 2 / 3, z + l]
        z_coords = [y, y + h / 2, y + h]

        vertices = list(itertools.product(x_coords, y_coords, z_coords))
        return [self.spaceToScreen(*v) for v in vertices]

    def drawPattern(
        self,
        draw: ImageDraw.ImageDraw,
        pattern: tuple[tuple],
        projected: list[tuple],
        colorRGB: tuple[int, int, int] | None,
        fill: ImageDraw._Ink | None,
        outline: ImageDraw._Ink | None,
    ):
        for face in pattern:
            draw.polygon(
                [
                    projected[face[0]],
                    projected[face[1]],
                    projected[face[2]],
                    projected[face[3]],
                ],
                fill=(
                    (
                        tuple(int(v * face[4]) for v in colorRGB)
                        if face[4] != -1
                        else None
                    )
                    if colorRGB
                    else fill
                ),
                outline=outline,
            )

    def draw_iso(
        self,
        x,
        y,
        z,
        w,
        l,
        h,
        color,
        pattern: tuple[tuple],
        clipping: list[schemas.drawObj] = [],
    ):
        """
        Draw a cube in isometric view with optional clipping region.

        Args:
            clip_region: Optional tuple (xmin, xmax, ymin, ymax) in screen coordinates
        """
        # Project all vertices to 2D
        projected = self.getProjected(x, y, z, w, l, h)

        colorRGB = ImageColor.getrgb(color)

        # Create a temporary image if clipping is needed
        if clipping:
            # Create mask for clipping
            mask = Image.new("L", self.image.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            self.drawPattern(mask_draw, pattern, projected, None, 255, 255)
            for clip in clipping:
                cx, cy, cz, cw, cl, ch, _, cpattern, _ = self.getPattern(clip)
                cprojected = self.getProjected(cx, cy, cz, cw, cl, ch)
                self.drawPattern(mask_draw, cpattern, cprojected, None, 0, 0)

            # Create temporary image for this object
            temp_img = Image.new("RGBA", self.image.size, (0, 0, 0, 0))
            temp_draw = ImageDraw.Draw(temp_img)
            self.drawPattern(temp_draw, pattern, projected, colorRGB, None, "black")

            # Composite with clipping
            self.image.paste(temp_img, None, mask)
        else:
            # Draw normally without clipping
            self.drawPattern(self.draw, pattern, projected, colorRGB, None, "black")

    masterOrder: dict[Literal["product", "sim_batch", "pallet", "container"], int] = {
        "container": 0,
        "sim_batch": 1,
        "pallet": 1,
        "product": 2,
    }

    def getPattern(self, obj: schemas.drawObj) -> tuple[
        float,
        float,
        float,
        float,
        float,
        float,
        str,
        tuple[tuple],
        list[schemas.drawObj],
    ]:
        w, l, h = model.getRotDim(obj.width, obj.length, obj.height, obj.rotation)
        x, y, z, color = obj.x, obj.z, obj.y, obj.color
        match obj.mastertype:
            case "product":
                return (x, y, z, w, l, h, color, self.CUBE_PATTERNS, obj.clipping)
            case "container":
                return (
                    x,
                    y,
                    z,
                    obj.load_width,
                    obj.load_length,
                    obj.load_height,
                    color,
                    self.CONTAINER_PATTERNS,
                    obj.clipping,
                )
            case "pallet" | "sim_batch":
                return (x, y, z, w, l, h, color, self.PALLET_PATTERNS, obj.clipping)
            case _:
                return (x, y, z, w, l, h, color, self.CUBE_PATTERNS, None)

    def render_scene(self):
        # Sorted cubes by position
        for simobject in self.objects:
            self.draw_iso(*self.getPattern(simobject))
