import { CameraControls, Environment, Grid, PerspectiveCamera } from "@react-three/drei"
import { useEffect, useRef } from "react"
import { PalletModel } from "./models/PalletModel"
import { BoxModel } from "./models/BoxModel"
import { Mesh, PerspectiveCamera as threePerspectiveCamera } from "three"
import { ShipContainerModel } from "./models/ShipContainerModel"
import { useThree } from "@react-three/fiber"
import { SimBatch } from "./SimCanvas"
import { getRotDim } from "./models/MoveModel"

interface SceneProps {
    data: SimBatch
    setImage: (screenshot: string) => void
}

const SceneStatic = ({
    data,
    setImage
}: SceneProps) => {
    // reference to 3D objects to reset camera
    const controlsRef = useRef<CameraControls>(null)
    const containerRef = useRef<Mesh>(null) // 3D reference for the container

    const unitScale = 1
    const renderScale = Math.max(data.length, data.width, data.height, data.loadheight, data.loadlength, data.loadwidth) / unitScale

    const screenShotRef = useRef<threePerspectiveCamera>(null) // 3D reference for the container

    const { gl, scene } = useThree()

    const allItems = data?.details.map((detail) => {
        if (detail.mastertype === "sim_batch") return detail
        else {
            return detail.products
        }
    }).flat()

    useEffect(() => {
        if (screenShotRef.current) {
            gl.render(scene, screenShotRef.current)
            const screenshot = gl.domElement.toDataURL()
            setImage(screenshot)
        }
    }, [data, screenShotRef.current, controlsRef.current])

    const adjustScale = (size: [number, number, number]): [number, number, number] => {
        return size.map(v => v / renderScale) as [number, number, number]
    }


    const adjustPos = (pos: [number, number, number], size: [number, number, number], contSize: [number, number, number]): [number, number, number] => {
        return [
            (pos[0] + ((size[0] - contSize[0]) / 2)),
            (pos[1] + ((size[1]) / 2)),
            (pos[2] + ((size[2] - contSize[2]) / 2))
        ]
    }

    return (
        <>
            <CameraControls makeDefault enabled={false} ref={controlsRef} />
            <PerspectiveCamera makeDefault position={[
                (data.length / renderScale),
                ((data.height + (data.batchtype === "pallet" ? data.loadheight : 0)) / renderScale),
                (data.width / renderScale)
            ]} fov={60} ref={screenShotRef} />
            <Environment preset="warehouse" />
            <Grid
                args={[2000, 2000]}
                position={[0, -0.5, 0]}
                cellSize={renderScale / 10}
                cellColor={'#6f6f6f'}
                sectionSize={100}
                sectionColor={'#9d4b4b'}
                fadeDistance={1000}
                fadeStrength={0.5}
                renderOrder={-1}
            />
            {data && allItems && <>
                <group position={[0, -0.5, 0]}>
                    {allItems.map((detail, detailIdx) => {
                        const boxPos = adjustScale(adjustPos(
                            [
                                detail.position[0],
                                detail.position[2],
                                detail.position[1]
                            ],
                            getRotDim(detail),
                            [data.loadlength, data.loadheight, data.loadwidth]
                        ))
                        return (
                            <group key={detailIdx} position={boxPos}>
                                {detail.mastertype === "product" &&
                                    <BoxModel
                                        data={detail}
                                        renderScale={renderScale}
                                    />}
                                {detail.mastertype === "sim_batch" &&
                                    <group position={[0, -(detail.loadheight - detail.height) / 2 / renderScale, 0]}>
                                        <PalletModel
                                            data={detail}
                                            renderScale={renderScale}
                                        />
                                        {detail.orders.map(order => {
                                            return order.products.map((product, idx) => {
                                                return (<BoxModel
                                                    key={idx}
                                                    data={product}
                                                    renderScale={renderScale}
                                                    position={[
                                                        (product.position[0] + (product.length - detail.loadlength) / 2) / renderScale,
                                                        ((product.position[1] + product.height / 2) / renderScale),
                                                        (product.position[2] + (product.width - detail.loadwidth) / 2) / renderScale
                                                    ]}
                                                />)
                                            })
                                        })}
                                    </group>
                                }
                            </group>
                        )
                    })
                    }
                </group>
                {(data.batchtype === "pallet" &&
                    <PalletModel
                        meshRef={containerRef}
                        data={data}
                        renderScale={renderScale}
                        position={[0, -0.5, 0]}
                    />)}
                {(data.batchtype === "container" &&
                    <ShipContainerModel
                        meshRef={containerRef}
                        isSeethrough
                        data={data}
                        renderScale={renderScale}
                        position={[0, -0.5, 0]}
                    />)}
            </>}
        </>
    )
}

export default SceneStatic