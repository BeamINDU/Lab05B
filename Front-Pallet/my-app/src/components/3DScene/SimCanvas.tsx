"use client"

import { Canvas } from "@react-three/fiber"
import Scene from "./Scene"
import { Focus, Package, PackageOpen, Rotate3D } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { CameraControls } from "@react-three/drei"
import { Mesh } from "three"

export interface SimProduct {
    batchdetailid: number
    masterid: number
    mastertype: 'product'
    code: string
    name: string
    length: number
    width: number
    height: number
    maxstack: number
    isfragile: boolean
    istop: boolean
    notstack: boolean
    issideUp: boolean
    color: string
    position: [number, number, number]
    rotation: 0 | 1 | 2 | 3 | 4 | 5
    no?:number
    qtt:number
}

export interface SimPallet {
    batchdetailid: number
    masterid: number
    mastertype: 'sim_batch'
    code: string
    name: string
    length: number
    width: number
    height: number
    loadlength: number
    loadwidth: number
    loadheight: number
    color: string
    position: [number, number, number]
    rotation: 0 | 1 | 2 | 3 | 4 | 5
    orders: SimOrder[]
}

export interface SimOrder {
    mastertype: undefined
    orderid: number
    ordername: string
    ordernumber: string
    products: SimProduct[]
}

export interface SimBatch {
    batchid: number
    batchname: string
    batchtype: 'pallet' | 'container'
    length: number
    width: number
    height: number
    loadlength: number
    loadwidth: number
    loadheight: number
    color: string

    details: (SimOrder | SimPallet)[]
}

interface SimCanvasProps {
    dataState: [SimBatch | undefined, (data: SimBatch | undefined) => void]
    selectedItemState: [SimProduct | SimPallet | undefined, (state: SimProduct | SimPallet | undefined) => void]
}

const SimCanvas = ({
    dataState,
    selectedItemState
}: SimCanvasProps) => {
    const [data, setData] = dataState
    const [selectedItem, setselectedItem] = selectedItemState
    const [isSeethrough, setisSeeThrough] = useState(true)
    const [isEdit, setisEdit] = useState(false)

    // reference to 3D objects to reset camera
    const controlsRef = useRef<CameraControls>(null)
    const containerRef = useRef<Mesh>(null) // 3D reference for the container

    // maximum render height for layer by layer slider
    const [maxRenderh, setmaxRenderh] = useState(100)

    // render scale so the pallet fits
    const [renderScale, setRenderScale] = useState<number>(2)
    const unitScale = 1


    useEffect(() => {
        setselectedItem(undefined)

        // reset camera
        if (containerRef.current) {
            controlsRef.current?.fitToSphere(containerRef.current, true)
        } else {
            controlsRef.current?.reset(true)
        }

        // reset max render height
        setmaxRenderh(100)

        // set render scale to reduce render distance
        setRenderScale((data && Math.max(data.length, data.width, data.height, data.loadheight, data.loadlength, data.loadwidth) / unitScale) ?? 2)
    }, [data?.batchid])

    // used to rotate item
    const rotH: { [r: number]: 0 | 1 | 2 | 3 | 4 | 5 } = {
        0: 1,
        1: 0,
        2: 3,
        3: 2,
        4: 5,
        5: 4,
    }
    const rotV: { [r: number]: 0 | 1 | 2 | 3 | 4 | 5 } = {
        0: 4,
        1: 3,
        2: 5,
        3: 1,
        4: 0,
        5: 2,
    }


    return (
        <div className="relative h-full w-full">
            <Canvas shadows gl={{ antialias: true, stencil: true, alpha: true }}>
                <Scene
                    dataState={dataState}
                    selectedItemState={selectedItemState}
                    isSeethrough={isSeethrough}
                    controlsRef={controlsRef}
                    containerRef={containerRef}
                    maxRenderh={maxRenderh}
                    renderScale={renderScale}
                    isEdit={isEdit}
                />
            </Canvas>

            <div className="absolute top-0 right-0 z-10 m-2 flex flex-row gap-2">
                <div className="flex items-center space-x-2 bg-background rounded-md p-2 border">
                    <input id="edit" type="checkbox" checked={isEdit} onChange={() => setisEdit(!isEdit)} />
                    <label htmlFor="edit" className="select-none">Edit</label>
                </div>
            </div>

            <div className="absolute right-0 bottom-0 h-1/2 m-2 mr-5 z-10">
                <input
                    type="range"
                    min='0'
                    max='100'
                    value={maxRenderh}
                    onChange={(e) => setmaxRenderh(+e.target.value)}
                    className="[writing-mode:vertical-lr] [direction:rtl] h-full"
                />
            </div>

            <div className="absolute bottom-0 left-0 z-10 m-2 flex flex-row gap-2">
                <button
                    className={"z-20"}
                    onClick={() => {
                        if (containerRef.current) {
                            controlsRef.current?.fitToSphere(containerRef.current, true)
                            return
                        }
                        controlsRef.current?.reset(true)
                    }}>
                    <Focus />
                </button>


                {data?.batchtype === "container" &&
                    <button
                        className={"z-20"}
                        onClick={() => {
                            setisSeeThrough(!isSeethrough)
                        }}>
                        {isSeethrough ? <Package /> : <PackageOpen />}
                    </button>
                }

                {data && selectedItem !== undefined && isEdit &&
                    <div className="z-0 flex flex-row gap-2">
                        <button
                            className={"z-20"}
                            onClick={() => {
                                if (!selectedItem) return
                                const newDetails = data.details.map((detail) => {
                                    if (selectedItem.mastertype === "sim_batch") {
                                        if (detail.mastertype !== "sim_batch") return detail
                                        if (detail.batchdetailid !== selectedItem.batchdetailid) return detail
                                        return {
                                            ...detail,
                                            rotation: rotH[detail.rotation],
                                        }
                                    } else {
                                        if (detail.mastertype) return detail
                                        return {
                                            ...detail,
                                            products: detail.products.map((product) => {
                                                if (product.batchdetailid !== selectedItem.batchdetailid) return product
                                                return {
                                                    ...product,
                                                    rotation: rotH[product.rotation],
                                                }
                                            })
                                        }
                                    }
                                })
                                setData({
                                    ...data,
                                    details: newDetails
                                })
                            }}>
                            <Rotate3D />
                        </button>
                        {selectedItem.mastertype !== "sim_batch" && <button
                            className={"z-20"}
                            onClick={() => {
                                if (!selectedItem) return
                                // if (selectedItem.mastertype === "sim_batch") return
                                const newDetails = data.details.map((detail) => {
                                    if (detail.mastertype) return detail
                                    return {
                                        ...detail,
                                        products: detail.products.map((product) => {
                                            if (product.batchdetailid !== selectedItem.batchdetailid) return product
                                            return {
                                                ...product,
                                                rotation: rotV[product.rotation],
                                            }
                                        })
                                    }
                                })
                                setData({
                                    ...data,
                                    details: newDetails
                                })
                            }}>
                            <Rotate3D className="rotate-90" />
                        </button>}
                    </div>}
            </div>
        </div >
    )
}

export default SimCanvas