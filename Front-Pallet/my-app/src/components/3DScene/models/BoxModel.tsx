import * as THREE from 'three'
import { Text, useGLTF } from '@react-three/drei'
import { GLTF } from 'three-stdlib'
import { ThreeElements } from '@react-three/fiber'
import { SimProduct } from '../SimCanvas'

function getBoxOrien(rotation: number): [number, number, number] {
  switch (rotation) {
    case 1:
      return [0, Math.PI / 2, 0]
    case 2:
      return [0, 0, Math.PI / 2]
    case 5:
      return [Math.PI / 2, 0, Math.PI / 2]
    case 4:
      return [Math.PI / 2, 0, 0]
    case 3:
      return [Math.PI / 2, -Math.PI / 2, 0]
    default:
      return [0, 0, 0]
  }
}

type GLTFResult = GLTF & {
  nodes: {
    box_A: THREE.Mesh
  }
  materials: {
    citybits_texture: THREE.MeshStandardMaterial
  }
}


type boxprops = ThreeElements['group'] & {
  isTransparent?: boolean,
  data: SimProduct,
  renderScale: number,
}

export function BoxModel(props: boxprops) {
  const { nodes, materials } = useGLTF('/models/Box.glb') as GLTFResult
  // const newMaterial = materials.citybits_texture.clone()
  // const ref = useRef<THREE.Group<THREE.Object3DEventMap>>(null)

  const adjustScale = (size: [number, number, number]): [number, number, number] => {
    return size.map(v => v / props.renderScale) as [number, number, number]
  }

  const textOffsets: [number, number, number][] = [[0, 0, 0.5], [0.5, 0, 0], [0, 0, -0.5], [-0.5, 0, 0]]

  const boxSize: [number, number, number] = adjustScale([props.data.length, props.data.height, props.data.width])

  return (
    <group {...props} scale={boxSize} rotation={getBoxOrien(props.data.rotation)} dispose={null}>
      <mesh geometry={nodes.box_A.geometry} renderOrder={-2} >
        <meshStandardMaterial {...materials.citybits_texture} color={props.data.color} transparent opacity={props.isTransparent ? 0.5 : 1} />
      </mesh>
      {!props.isTransparent && textOffsets.map((offset, index) => {
        const text = props.data.name + "#" + props.data.batchdetailid
        return (
          < Text
            key={index}
            scale={10 / text.length}
            strokeWidth={"2%"}
            strokeColor={"white"}
            color={"black"}
            depthOffset={-1}
            fontSize={0.1}
            fontWeight={"bold"}
            position={offset}
            rotation={[0, Math.PI / 2 * index, 0]}
            renderOrder={-1}
          >
            {text}
          </Text>
        )
      })}
    </group>
  )
}


useGLTF.preload('/models/Box.glb')
