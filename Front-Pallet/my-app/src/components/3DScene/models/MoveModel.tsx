import * as THREE from 'three'
import { Edges, PivotControls, useGLTF } from '@react-three/drei'
import { ThreeElements } from '@react-three/fiber'
import { SimPallet, SimProduct } from '../SimCanvas'

type SimBox = SimPallet | SimProduct


export function getRotDim(item: SimBox): [number, number, number] {
  const loadHeight = item.mastertype === "sim_batch" ? item.loadheight : 0

  switch (item.rotation) {
    case 0:
      return [item.length, item.height + loadHeight, item.width]
    case 1:
      return [item.width, item.height + loadHeight, item.length]
    case 2:
      return [item.height + loadHeight, item.length, item.width]
    case 3:
      return [item.width, item.length, item.height + loadHeight]
    case 4:
      return [item.length, item.width, item.height + loadHeight]
    case 5:
      return [item.height + loadHeight, item.width, item.length]
    default:
      return [item.length, item.height + loadHeight, item.width]
  }
}



type boxprops = ThreeElements['group'] & {
  isSelected: boolean,
  isTransparent: boolean,
  isEdit: boolean,
  setItem: (item: SimBox) => void
  allItems: SimBox[],
  contSize: [number, number, number],
  data: SimBox,
  renderScale: number,
}

export function MoveModel(props: boxprops) {
  // const newMaterial = materials.citybits_texture.clone()
  // const ref = useRef<THREE.Group<THREE.Object3DEventMap>>(null)

  const adjustScale = (size: [number, number, number]): [number, number, number] => {
    return size.map(v => v / props.renderScale) as [number, number, number]
  }

  const readjustScale = (size: [number, number, number]): [number, number, number] => {
    return size.map(v => v * props.renderScale) as [number, number, number]
  }


  const adjustPos = (pos: [number, number, number], size: [number, number, number]): [number, number, number] => {
    return [
      (pos[0] + ((size[0] - props.contSize[0]) / 2)),
      (pos[1] + ((size[1]) / 2)),
      (pos[2] + ((size[2] - props.contSize[2]) / 2))
    ]
  }

  const readjustPos = (pos: [number, number, number], size: [number, number, number]): [number, number, number] => {
    return [
      (pos[0] - ((size[0] - props.contSize[0]) / 2)),
      (pos[1] - (size[1]) / 2),
      (pos[2] - ((size[2] - props.contSize[2]) / 2))
    ]
  }


  const boxSize: [number, number, number] = adjustScale([props.data.length, props.data.height + (props.data.mastertype === "sim_batch" ? props.data.loadheight : 0), props.data.width])
  const boxOrien = adjustScale(getRotDim(props.data))
  const boxPos = adjustScale(adjustPos(
    [
      props.data.position[0],
      props.data.position[2],
      props.data.position[1]
    ],
    getRotDim(props.data)
  ))

  // collision on rotations is buggy :/
  // useEffect(() => {
  //   const newPosition = new THREE.Vector3().setFromMatrixPosition(matrix).clamp(min, max)
  //   const newPosArray = newPosition.toArray()
  //   const allBoxes = [...data.simData[props.selectedPallet].boxes].map((box) => {
  //     return {
  //       id: box.id,
  //       type: box.type,
  //       orien: box.orien?.map(dim => dim * props.gridScale) as [number, number, number],
  //       pos: box.pos?.map(dim => dim * props.gridScale) as [number, number, number],
  //     }
  //   })
  //   const tempPosArray = getNewPos(allBoxes, newPosArray)
  //   const newPosVec = new THREE.Vector3(...tempPosArray)
  //   matrix.copy(matrix.setPosition(newPosVec))
  // }, [boxOrien])

  const matrix = new THREE.Matrix4().setPosition(new THREE.Vector3(...boxPos))
  const adjustedContSize = adjustScale(props.contSize)

  const pallet_min = [(boxOrien[0] - adjustedContSize[0]) / 2, (boxOrien[1] / 2), (boxOrien[2] - adjustedContSize[2]) / 2]
  const pallet_max = [(adjustedContSize[0] - boxOrien[0]) / 2, adjustedContSize[1] - (boxOrien[1] / 2), (adjustedContSize[2] - boxOrien[2]) / 2]
  const min = new THREE.Vector3(...pallet_min);
  const max = new THREE.Vector3(...pallet_max);

  const pallet_minmax = [pallet_min[0], pallet_max[0], pallet_min[1], pallet_max[1], pallet_min[2], pallet_max[2]]

  function getNewPos(boxes: SimBox[], PosArray: [number, number, number], newPosArray?: [number, number, number]) {
    if (!newPosArray) newPosArray = PosArray;
    const PosArray_min: [number, number, number] = [newPosArray[0] - (boxOrien[0] / 2), newPosArray[1] - (boxOrien[1] / 2), newPosArray[2] - (boxOrien[2] / 2)]
    const PosArray_max: [number, number, number] = [newPosArray[0] + (boxOrien[0] / 2), newPosArray[1] + (boxOrien[1] / 2), newPosArray[2] + (boxOrien[2] / 2)]

    const { intersectingBox, index } = boxes.reduce((ret: { intersectingBox: SimBox | null, index: number | null }, box, index) => {
      if (!(box.batchdetailid === props.data.batchdetailid)) {
        const rotatedDim = adjustScale(getRotDim(box))
        const box_pos = adjustScale(adjustPos([box.position[0], box.position[2], box.position[1]], getRotDim(box)))
        const box_min = [box_pos[0] - (rotatedDim[0] / 2), box_pos[1] - (rotatedDim[1] / 2), box_pos[2] - (rotatedDim[2] / 2)]
        const box_max = [box_pos[0] + (rotatedDim[0] / 2), box_pos[1] + (rotatedDim[1] / 2), box_pos[2] + (rotatedDim[2] / 2)]// check intersections
        if (!(
          (box_min[0] >= PosArray_max[0] || PosArray_min[0] >= box_max[0]) ||
          (box_min[1] >= PosArray_max[1] || PosArray_min[1] >= box_max[1]) ||
          (box_min[2] >= PosArray_max[2] || PosArray_min[2] >= box_max[2])
        )) {
          return { intersectingBox: box, index }
        }
      }
      return ret
    }, { intersectingBox: null, index: null })

    if (intersectingBox === null || index === null) return newPosArray

    const intBoxRotDim = adjustScale(getRotDim(intersectingBox))
    const intBoxPos = adjustScale(adjustPos([intersectingBox.position[0], intersectingBox.position[2], intersectingBox.position[1]], getRotDim(intersectingBox)))
    const box_min = [intBoxPos[0] - (intBoxRotDim[0] / 2), intBoxPos[1] - (intBoxRotDim[1] / 2), intBoxPos[2] - (intBoxRotDim[2] / 2)]
    const box_max = [intBoxPos[0] + (intBoxRotDim[0] / 2), intBoxPos[1] + (intBoxRotDim[1] / 2), intBoxPos[2] + (intBoxRotDim[2] / 2)]// check intersections

    const adjustedPos = [
      box_min[0] - (boxOrien[0] / 2), box_max[0] + (boxOrien[0] / 2),
      box_min[1] - (boxOrien[1] / 2), box_max[1] + (boxOrien[1] / 2),
      box_min[2] - (boxOrien[2] / 2), box_max[2] + (boxOrien[2] / 2)]

    const min_intersection = [
      PosArray_max[0] - box_min[0], box_max[0] - PosArray_min[0],
      PosArray_max[1] - box_min[1], box_max[1] - PosArray_min[1],
      PosArray_max[2] - box_min[2], box_max[2] - PosArray_min[2]]
      .reduce((ret: [number | null, number | null], intersect, id) => {
        if (newPosArray[Math.floor(id / 2)] !== PosArray[Math.floor(id / 2)]) {
          return ret
        }
        if (id % 2 === 0 && pallet_minmax[id] > adjustedPos[id]) {
          return ret
        }
        if (id % 2 === 1 && pallet_minmax[id] < adjustedPos[id]) {
          return ret
        }
        if (ret[1] === null) return [id, intersect] as [number, number]
        if (intersect > 0 && ret[1] > intersect) {
          return [id, intersect] as [number, number]
        }
        return ret
      }, [null, null])

    if (min_intersection[0] === null) return getNewPos(boxes.filter((element, i) => i !== index), PosArray, new THREE.Vector3().setFromMatrixPosition(matrix).toArray())

    const tempPosArray = newPosArray.map((dim, id) => {
      if (min_intersection[0] !== null && id === Math.floor(min_intersection[0] / 2)) {
        return adjustedPos[min_intersection[0]]
      }
      return dim
    }) as [number, number, number]


    return getNewPos(boxes.filter((element, i) => i !== index), PosArray, tempPosArray)
  }

  return (
    <PivotControls
      scale={Math.max(...boxSize) >= 1 / props.renderScale ? Math.max(...boxSize) : 1}
      matrix={matrix}
      autoTransform={false}
      onDrag={(matrix_: THREE.Matrix4) => {
        const newPosition = new THREE.Vector3().setFromMatrixPosition(matrix_).clamp(min, max)
        const newPosArray = newPosition.toArray()
        const allBoxes = props.allItems
        const tempPosArray = getNewPos(allBoxes, newPosArray)
        const newPosVec = new THREE.Vector3(...tempPosArray)
        matrix.copy(matrix_.setPosition(newPosVec))

      }}
      onDragEnd={() => {
        const position = new THREE.Vector3().setFromMatrixPosition(matrix).toArray()
        const convertPos = readjustPos(readjustScale(position), getRotDim(props.data))
        const newBox: SimBox = {
          ...props.data,
          position: [convertPos[0], convertPos[2], convertPos[1]],
        }
        props.setItem(newBox)
      }}
      depthTest={false}
      offset={[-(boxOrien[0] / 2), -(boxOrien[1] / 2), -(boxOrien[2] / 2)]} disableRotations disableScaling
      disableAxes={!(props.isSelected && props.isEdit)}
      disableSliders={!(props.isSelected && props.isEdit)}
      visible={(props.isSelected && props.isEdit)}
    >
      <group {...props} dispose={null}>

        {props.children}

        {props.isSelected &&
          <mesh scale={boxSize}>
            <boxGeometry />
            <meshStandardMaterial transparent opacity={0} />
            <Edges lineWidth={2} scale={1.02} color={"black"} />
          </mesh>
        }
      </group>
    </PivotControls >
  )
}


useGLTF.preload('/models/Box.glb')
