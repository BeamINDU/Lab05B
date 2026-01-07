'use client'
import { Canvas } from "@react-three/fiber"
import SceneStatic from "./SceneStatic"
import { Dispatch, SetStateAction } from "react"
import { SimBatch } from "./SimCanvas"

interface SimCanvasProps {
    data: SimBatch[] | undefined
    setImage: Dispatch<SetStateAction<{
        [id: string]: string;
    }>>
    children: React.ReactNode
}

const SimCanvasStatic = ({ data, setImage, children }: SimCanvasProps) => {
    return (
        <div className="relative flex flex-col gap-2 w-full h-full justify-center items-center">
            {data?.map((container) => {
                return (
                    <div key={container.batchid}>
                        <Canvas shadows gl={{ antialias: true, stencil: true, alpha: true }}>
                            <SceneStatic
                                data={container}
                                setImage={(screenshot: string) => {
                                    setImage((images: { [id: string]: string }) => ({
                                        ...images,
                                        [container.batchid]: screenshot
                                    }))
                                }}
                            />
                        </Canvas>
                    </div>
                )
            })}
            <div className="absolute w-full h-full bg-white">
                {children}
            </div>
        </div>
    )
}
export default SimCanvasStatic