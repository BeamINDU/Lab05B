import {
  CameraControls,
  Environment,
  Grid,
  PerspectiveCamera,
} from "@react-three/drei";
import { RefObject } from "react";
import { PalletModel } from "./models/PalletModel";
import { Mesh } from "three";
import { ShipContainerModel } from "./models/ShipContainerModel";
import { SimBatch, SimPallet, SimProduct } from "./SimCanvas";
import { MoveModel } from "./models/MoveModel";
import { BoxModel } from "./models/BoxModel";

interface SceneProps {
  dataState: [SimBatch | undefined, (data: SimBatch | undefined) => void];
  controlsRef: RefObject<CameraControls>;
  containerRef: RefObject<Mesh>;
  selectedItemState: [
    SimProduct | SimPallet | undefined,
    (state: SimProduct | SimPallet | undefined) => void
  ];
  maxRenderh: number;
  isSeethrough: boolean;
  renderScale: number;
  isEdit: boolean;
}

const Scene = ({
  dataState: [data, setData],
  controlsRef,
  containerRef,
  selectedItemState: [selectedItem, setselectedItem],
  maxRenderh,
  isSeethrough,
  renderScale,
  isEdit,
}: SceneProps) => {
  const allItems = data?.details.map((detail) => {
    if (detail.mastertype === "sim_batch") return detail
    else {
        return detail.products
    }
}).flat()

  function setItem(item: SimProduct | SimPallet) {
    if (!data) return;

    const newDetails = data.details.map((detail) => {
      if (item.mastertype === "sim_batch") {
        if (detail.mastertype !== "sim_batch") return detail;
        if (detail.batchdetailid !== item.batchdetailid) return detail;
        return item;
      } else {
        if (detail.mastertype) return detail;
        return {
          ...detail,
          products: detail.products.map((product) => {
            if (product.batchdetailid !== item.batchdetailid) return product;
            return item;
          }),
        };
      }
    });

    setData({
      ...data,
      details: newDetails,
    });
  }

  return (
    <>
      <CameraControls
        makeDefault
        ref={controlsRef}
        minPolarAngle={0}
        maxPolarAngle={Math.PI / 2}
      />
      <PerspectiveCamera makeDefault position={[0, 0, 5]} fov={60} />
      <Environment preset="warehouse" />
      <Grid
        args={[2000, 2000]}
        position={[0, -0.5, 0]}
        cellSize={renderScale / 10}
        cellColor={"#6f6f6f"}
        sectionSize={100}
        sectionColor={"#9d4b4b"}
        fadeDistance={1000}
        fadeStrength={0.5}
        renderOrder={-1}
      />
      {data && allItems && (
        <>
          <group
            onPointerMissed={() => {
              setselectedItem(undefined);
            }}
            position={[0, -0.5, 0]}
          >
            {allItems.map((detail, detailIdx) => {
              if (detail.position[2] > (data.height * maxRenderh) / 100) return;
              return (
                <MoveModel
                  key={detailIdx}
                  onClick={(e) => {
                    e.stopPropagation();
                    setselectedItem(detail);
                  }}
                  contSize={[data.loadlength, data.loadheight, data.loadwidth]}
                  isSelected={
                    selectedItem !== undefined &&
                    selectedItem.batchdetailid === detail.batchdetailid
                  }
                  isTransparent={
                    selectedItem !== undefined &&
                    selectedItem.batchdetailid !== detail.batchdetailid
                  }
                  isEdit={isEdit}
                  setItem={setItem}
                  allItems={allItems}
                  data={detail}
                  renderScale={renderScale}
                >
                  {detail.mastertype === "product" && (
                    <BoxModel
                      data={detail}
                      renderScale={renderScale}
                      isTransparent={
                        selectedItem !== undefined &&
                        selectedItem.batchdetailid !== detail.batchdetailid
                      }
                    />
                  )}
                  {detail.mastertype === "sim_batch" && (
                    <group
                      position={[
                        0,
                        -(detail.loadheight - detail.height) / 2 / renderScale,
                        0,
                      ]}
                    >
                      <PalletModel data={detail} renderScale={renderScale} />
                      {detail.orders.map((order) => {
                        return order.products.map((product, idx) => {
                          return (
                            <BoxModel
                              key={idx}
                              data={product}
                              renderScale={renderScale}
                              position={[
                                (product.position[0] +
                                  (product.length - detail.loadlength) / 2) /
                                  renderScale,
                                (product.position[2] + product.height / 2) /
                                  renderScale,
                                (product.position[1] +
                                  (product.width - detail.loadwidth) / 2) /
                                  renderScale,
                              ]}
                            />
                          );
                        });
                      })}
                    </group>
                  )}
                </MoveModel>
              );
            })}
          </group>
          {data.batchtype === "pallet" && (
            <PalletModel
              meshRef={containerRef}
              data={data}
              renderScale={renderScale}
              position={[0, -0.5, 0]}
            />
          )}
          {data.batchtype === "container" && (
            <ShipContainerModel
              meshRef={containerRef}
              isSeethrough={isSeethrough}
              data={data}
              renderScale={renderScale}
              position={[0, -0.5, 0]}
            />
          )}
        </>
      )}
    </>
  );
};

export default Scene;
