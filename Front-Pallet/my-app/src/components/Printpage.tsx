// 'use client';

// import { Canvas } from "@react-three/fiber";
// import SceneStatic from "./3DScene/SceneStatic";
// import { SimContainer } from "./3DScene/SimCanvas";
// import { useState, useEffect } from "react";

// const PrintPage = ({ data, setImageData }: { data: SimContainer[], setImageData: (img: { [id: string]: string }) => void }) => {
//     const [image, setImage] = useState<{ [id: string]: string }>({});

//     useEffect(() => {
//         setImageData(image);
//     }, [image, setImageData]);

//     return (
//         <div className="flex flex-row justify-evenly items-center w-full h-full">
//             <div className="flex flex-col gap-2 w-full justify-center items-center">
//                 {data.map((container) => (
//                     <div key={container.id}>
//                         <Canvas shadows gl={{ antialias: true, stencil: true, alpha: true }}>
//                             <SceneStatic
//                                 data={container}
//                                 isPallet={true}
//                                 setImage={(screenshot: string) => {
//                                     setImage((i) => ({
//                                         ...i,
//                                         [container.id]: screenshot
//                                     }));
//                                 }}
//                             />
//                         </Canvas>
//                     </div>
//                 ))}
//             </div>
//             <div className="flex flex-col gap-2 w-full justify-center items-center">
//                 {data.map((container) => (
//                     <div key={container.id}>
//                         <img src={image[container.id]} alt="image" width={250} height={250} />
//                     </div>
//                 ))}
//             </div>
//         </div>
//     );
// };

// export default PrintPage;
