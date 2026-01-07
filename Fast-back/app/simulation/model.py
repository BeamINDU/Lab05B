import pygad
import numpy as np
from typing import List, Tuple, Dict, Literal, TypedDict


class Item:
    def __init__(
        self,
        id: str,
        order_id: str,
        itemType_id: str,
        length: float,
        width: float,
        height: float,
        weight: float,
        isSideUp: bool,
        maxStack: int,
        itemType: str,
        grounded: bool = False,
        priority: int = 1,
    ):
        self.order_id: str = order_id
        self.id: str = id
        self.itemType_id: str = itemType_id
        self.itemType: str = itemType
        self.length: float = length
        self.width: float = width
        self.height: float = height
        self.weight: float = weight
        self.isSideUp: bool = isSideUp
        self.maxStack: int = maxStack
        self.priority: int = priority
        self.grounded: bool = grounded
        self.position: Tuple[float, float, float] = None
        self.rotation: Literal[0, 1, 2, 3, 4, 5] = 0
        self.container_id: str = None  # Assigned container

    def get_rotated_dimensions(self) -> Tuple[float, float, float]:
        # Get item dimensions after rotation.
        match self.rotation:
            case 0:
                return (self.length, self.width, self.height)
            case 1:
                return (self.width, self.length, self.height)
            case 2:
                return (self.height, self.width, self.length)
            case 3:
                return (self.width, self.height, self.length)
            case 4:
                return (self.length, self.height, self.width)
            case 5:
                return (self.height, self.length, self.width)
            case _:
                return (self.length, self.width, self.height)


class Container:

    def __init__(
        self,
        id: str,  # individual container id
        type_id: str,  # pallet/container master id
        length: float,
        width: float,
        height: float,
        max_weight: float,
        exlength: float,
        exwidth: float,
        exheight: float,
        exweight: float,
        priority: int = 1,
    ):
        self.id: str = id
        self.type_id: str = type_id
        self.length: float = length
        self.width: float = width
        self.height: float = height

        self.exlength: float = exlength
        self.exwidth: float = exwidth
        self.exheight: float = exheight
        self.exweight: float = exweight

        self.max_weight: float = max_weight
        self.priority: int = priority  # Priority for container selection
        self.items: List[Item] = []
        self.total_weight: float = 0


class MultiContainerAssignGA:
    def __init__(self, containers: List[Container], items: List[Item]) -> None:

        containers_sorted = sorted(containers, key=lambda x: x.priority, reverse=True)
        total_items_weight = sum(item.weight for item in items)
        total_items_volumn = sum(
            item.length * item.width * item.height for item in items
        )

        total_max_weight = 0
        total_cont_volumn = 0
        self.containers = []
        for container in containers_sorted.copy():
            if (
                total_max_weight > total_items_weight
                and total_cont_volumn > total_items_volumn
            ):
                break
            self.containers.append(containers_sorted.pop(0))
            total_max_weight += container.max_weight - container.total_weight
            total_cont_volumn += (
                container.length * container.height * container.width
                - sum(
                    item.width * item.length * item.height for item in container.items
                )
            )
        self.unused_containers = containers_sorted

        self.initial_items = [container.items for container in self.containers]
        self.initial_weight = [container.total_weight for container in self.containers]

        self.items = items
        self.max_item_priority: float = (
            max(item.priority for item in items) * len(items) or 1
        )
        self.max_cont_priority: float = max(cont.priority for cont in containers) or 1

        # Initialize GA parameters
        self.num_generations = 500
        self.num_parents_mating = 10
        self.num_solutions = 20
        self.mutation_percent = 10
        self.init_ga()

    def init_ga(self):
        # Genes: [container_idx] for each item
        num_genes = len(self.items)
        max_range = len(self.containers)

        self.ga_instance = pygad.GA(
            num_generations=self.num_generations,
            num_parents_mating=self.num_parents_mating,
            num_genes=num_genes,
            sol_per_pop=self.num_solutions,
            init_range_low=0,
            init_range_high=max_range,
            gene_space={"low": 0, "high": max_range, "step": 1},
            mutation_percent_genes=self.mutation_percent,
            mutation_type="random",
            crossover_type="single_point",
            fitness_func=self.fitness_func,
        )

    def decode_solution(self, solution: List[int]) -> List[Container]:
        # Decode GA solution into container assignments.
        # reset containers total weights and items
        for i, container in enumerate(self.containers):
            container.items = self.initial_items[i].copy()
            container.total_weight = self.initial_weight[i]

        for item_idx, gene in enumerate(solution):
            container = self.containers[int(gene)]
            self.items[item_idx].container_id = container.id
            container.items.append(self.items[item_idx])
            container.total_weight += self.items[item_idx].weight

        return self.containers

    def fitness_func(self, instance, solution, solution_idx):
        # Calculate fitness of a solution.
        fitness = 0
        sol_containers = self.decode_solution(solution)

        for container in sol_containers:
            container_fitness = 0
            items: List[Item] = container.items
            total_weight: float = container.total_weight

            if len(container.items) <= 0:
                continue

            weight_utilization = total_weight / container.max_weight

            # Weight constraint
            over_weight = 0
            if total_weight > container.max_weight:
                # print("overweight")
                over_weight = total_weight / container.max_weight

            # Calculate container utilization
            volume_utilization = sum(
                item.length * item.width * item.height for item in items
            ) / (container.length * container.width * container.height)

            over_volume = 0
            if volume_utilization > 1:
                over_volume = volume_utilization

            # Calculate priority satisfaction
            priority_score = (
                (sum(item.priority for item in items) / (self.max_item_priority))
                if items
                else 0
            )

            cont_priority_score = container.priority / self.max_cont_priority

            # Container-specific fitness
            container_fitness = (
                volume_utilization * 0.4
                + weight_utilization * 0.4
                + priority_score * 0.1
                + cont_priority_score * 0.1
            ) - (over_weight + over_volume)

            fitness += container_fitness

        # Normalize fitness by number of containers used
        used_containers = sum(
            1 for container in sol_containers if len(container.items) > 0
        )
        if used_containers > 0 and fitness > 0:
            fitness /= used_containers
        return fitness

    def run(self) -> Dict:
        # Run the genetic algorithm and return best solution.
        self.ga_instance.run()
        solution, solution_fitness, _ = self.ga_instance.best_solution()
        sol_containers = self.decode_solution(solution)

        # Decode and format the best solution
        result = {
            "fitness": solution_fitness,
            "containers": sol_containers + self.unused_containers,
        }

        return result


class ContainerLoadingSolution(TypedDict):
    fitness: float
    container: Container
    unused: List[Item]


class ContainerLoadingGA:
    def __init__(
        self,
        container: Container,
        items: List[Item],
        centered: bool = True,
    ):
        self.container = container
        self.centered = centered

        self.items = items
        if len(items) == 0:
            return
        self.max_priority: float = max(item.priority for item in items) or 1
        self.itemTypes = list({item.itemType_id for item in items})

        self.num_generations = 500
        self.num_parents_mating = 4
        self.num_solutions = 40
        self.low_mutation_percent = 70
        self.high_mutation_percent = 10
        # Initialize GA parameters
        self.init_ga()

    def init_ga(self):
        # Genes: [item_index, corner_placement] for each item
        num_genes = len(self.itemTypes) + len(self.items) * 2 * 2

        max_range = len(self.items) * 8  # For corners (item_index always lower)

        self.ga_instance = pygad.GA(
            num_generations=self.num_generations,
            num_parents_mating=self.num_parents_mating,
            num_genes=num_genes,
            sol_per_pop=self.num_solutions,
            init_range_low=0,
            init_range_high=max_range,
            gene_space={"low": 0, "high": max_range, "step": 1},
            mutation_percent_genes=[
                self.low_mutation_percent,
                self.high_mutation_percent,
            ],
            mutation_type="adaptive",
            crossover_type="single_point",
            fitness_func=self.fitness_func,
        )

    def check_collision(self, item1: Item, item2: Item) -> bool:
        # Check if two items collide in 3D space.
        if item1.position is None or item2.position is None:
            return False

        x1, y1, z1 = item1.position
        x2, y2, z2 = item2.position

        l1, w1, h1 = item1.get_rotated_dimensions()
        l2, w2, h2 = item2.get_rotated_dimensions()

        # return if overlap

        return (
            x1 < x2 + l2
            and x1 + l1 > x2
            and y1 < y2 + w2
            and y1 + w1 > y2
            and z1 < z2 + h2
            and z1 + h1 > z2
        )

    def supported_corner(self, item1: Item, item2: Item) -> int:
        # number of corners item1 is supported by item2
        if item1.position is None or item2.position is None:
            return 0

        x1, y1, z1 = item1.position

        # supported by the ground
        if z1 == 0:
            return 4

        l1, w1, h1 = item1.get_rotated_dimensions()

        x2, y2, z2 = item2.position
        l2, w2, h2 = item2.get_rotated_dimensions()

        # item2 is not directly underneath
        if z1 != z2 + h2:
            return 0

        bottom_corners = [
            (x1, y1),
            (x1 + l1, y1),
            (x1, y1 + w1),
            (x1 + l1, y1 + w1),
        ]

        # supported corners
        supported = 0
        for corner in bottom_corners:

            if (
                corner[0] >= x2
                and corner[0] <= x2 + l2
                and corner[1] >= y2
                and corner[1] <= y2 + w2
            ):
                supported += 1

        # return supported corners

        return supported

    def supported_SA(self, item1: Item, item2: Item) -> float:
        # get supported surface area of item1 by item2
        if item1.position is None or item2.position is None:
            return 0

        x1, y1, z1 = item1.position
        l1, w1, h1 = item1.get_rotated_dimensions()

        # supported by the ground
        if z1 == 0:
            return l1 * w1

        x2, y2, z2 = item2.position
        l2, w2, h2 = item2.get_rotated_dimensions()

        # item2 is not directly underneath
        if z1 != z2 + h2:
            return 0

        # return item1 surface area that is supported
        return max(0, min(x1 + l1, x2 + l2) - max(x1, x2)) * max(
            0, min(y1 + w1, y2 + w2) - max(y1, y2)
        )

    def check_outbound(self, item: Item):
        # Check container bounds
        l, w, h = item.get_rotated_dimensions()
        x, y, z = item.position

        if (
            x + l > self.container.length
            or y + w > self.container.width
            or z + h > self.container.height
            or x < 0
            or y < 0
            or z < 0
        ):
            return True
        return False

    def decode_solution(self, solution):
        # Decode GA solution into container assignments and item positions.

        # reset items
        self.container.items = []
        self.container.total_weight = 0

        itemTypesRotations = solution[: len(self.itemTypes)]
        itemGenes = solution[len(self.itemTypes) :]

        # each item has 2 genes [item_index, corner_placement]
        n = 2

        grouped_solution = [itemGenes[i : i + n] for i in range(0, len(itemGenes), n)]

        corner_vertices = []

        items = self.items.copy()
        # used to return raw solution without bad placements

        for genes in grouped_solution:

            if len(items) == 0:
                break

            # adjust the values to fit into countainer index
            item_idx = int(genes[0] % len(items))
            item = items[item_idx]

            # set item properties
            # item.rotation = int(genes[1] % 6)

            item.rotation = int(
                itemTypesRotations[self.itemTypes.index(item.itemType_id)]
                % (
                    2 if item.isSideUp else 6
                )  # isSideUp then item can only rotate horizontally
            )
            l, w, h = item.get_rotated_dimensions()

            valid_placement = False
            stackLimit = item.maxStack
            # set item positions
            if len(corner_vertices) > 0:
                corner_idx = int(genes[1] % len(corner_vertices))
                # container corner vertices: (offset, x, y, z)

                match corner_vertices[corner_idx][0]:
                    case 0 | 2 | 4:

                        item.position = corner_vertices[corner_idx][1:4]
                    case 3 | 6:
                        item.position = (
                            corner_vertices[corner_idx][1] - l,
                            corner_vertices[corner_idx][2],
                            corner_vertices[corner_idx][3],
                        )

                    case 1 | 5:
                        item.position = (
                            corner_vertices[corner_idx][1],
                            corner_vertices[corner_idx][2] - w,
                            corner_vertices[corner_idx][3],
                        )

                    case 7:
                        item.position = (
                            corner_vertices[corner_idx][1] - l,
                            corner_vertices[corner_idx][2] - w,
                            corner_vertices[corner_idx][3],
                        )
                    case _:

                        item.position = corner_vertices[corner_idx][1:4]

                # get stack hieght from previous corner
                if stackLimit < 0:
                    # item has no stack limit, uses the one from corner
                    stackLimit = corner_vertices[corner_idx][4]
                elif corner_vertices[corner_idx][4] >= 0:
                    # item and corner has stack limit
                    # chooses the least one to not violate the both limits
                    stackLimit = min(stackLimit, corner_vertices[corner_idx][4])

                grounded = item.position[2] == 0
                overlap = False
                supported_corners = 0
                supported_SA = 0

                # check valid placement
                for item2 in self.container.items:
                    if self.check_collision(item, item2):
                        overlap = True
                        break
                    supported_corners += self.supported_corner(item, item2)
                    supported_SA += self.supported_SA(item, item2)

                if (
                    (not overlap)
                    and (not item.grounded or (item.grounded and grounded))
                    and supported_corners > 2
                    and (supported_SA >= 0.7 * l * w)
                    and not self.check_outbound(item)
                ):
                    valid_placement = True

            else:
                item.position = (0, 0, 0)
                if not self.check_outbound(item):
                    valid_placement = True

            if not valid_placement:
                # no valid placement, skip this gene
                item.position = None
                item.rotation = 0
                continue

            # add new vertices
            new_cv = (
                [
                    (
                        0,
                        item.position[0] + l,
                        item.position[1],
                        item.position[2],
                        stackLimit,
                    ),
                    (
                        1,
                        item.position[0] + l,
                        item.position[1] + w,
                        item.position[2],
                        stackLimit,
                    ),
                    (
                        2,
                        item.position[0],
                        item.position[1] + w,
                        item.position[2],
                        stackLimit,
                    ),
                    (
                        3,
                        item.position[0] + l,
                        item.position[1] + w,
                        item.position[2],
                        stackLimit,
                    ),
                ]
                if stackLimit == 0  # current stack hieght is not 0
                else [
                    (
                        0,
                        item.position[0] + l,
                        item.position[1],
                        item.position[2],
                        stackLimit,
                    ),
                    (
                        1,
                        item.position[0] + l,
                        item.position[1] + w,
                        item.position[2],
                        stackLimit,
                    ),
                    (
                        2,
                        item.position[0],
                        item.position[1] + w,
                        item.position[2],
                        stackLimit,
                    ),
                    (
                        3,
                        item.position[0] + l,
                        item.position[1] + w,
                        item.position[2],
                        stackLimit,
                    ),
                    (
                        4,
                        item.position[0],
                        item.position[1],
                        item.position[2] + h,
                        stackLimit - 1 if stackLimit > 0 else -1,
                    ),
                    (
                        5,
                        item.position[0],
                        item.position[1] + w,
                        item.position[2] + h,
                        stackLimit - 1 if stackLimit > 0 else -1,
                    ),
                    (
                        6,
                        item.position[0] + l,
                        item.position[1],
                        item.position[2] + h,
                        stackLimit - 1 if stackLimit > 0 else -1,
                    ),
                    (
                        7,
                        item.position[0] + l,
                        item.position[1] + w,
                        item.position[2] + h,
                        stackLimit - 1 if stackLimit > 0 else -1,
                    ),
                ]
            )

            for vertex in new_cv:
                corner_vertices.append(vertex)

            # insert item into the container and remove it as avaliable
            self.container.items.append(item)
            self.container.total_weight += item.weight
            items.pop(item_idx)

        if len(self.container.items) == 0:
            return self.container

        if not self.centered:
            return self.container

        # adjust all item's positions to be in the middle of the container
        max_x = max(
            item.position[0] + item.get_rotated_dimensions()[0]
            for item in self.container.items
        )

        max_y = max(
            item.position[1] + item.get_rotated_dimensions()[1]
            for item in self.container.items
        )

        min_x = min(item.position[0] for item in self.container.items)
        min_y = min(item.position[1] for item in self.container.items)
        x_offset = (self.container.length - abs(max_x - min_x)) / 2
        y_offset = (self.container.width - abs(max_y - min_y)) / 2

        for item in self.container.items:
            item.position = (
                item.position[0] + x_offset - min_x,
                item.position[1] + y_offset - min_x,
                item.position[2],
            )

        return self.container

    def center_mass_score(self, containerSize: tuple[float, float, float], item: Item):
        x, y, z = item.position

        l, w, h = item.get_rotated_dimensions()
        cl, cw, ch = containerSize

        return item.weight * (
            (cl * (x + l / 2))
            - ((x + l / 2) * (x + l / 2))
            + (cw * (y + w / 2))
            - ((y + w / 2) * (y + w / 2))
            + (ch * ch * 10)
            - ((z + h / 2) * (z + h / 2) * 10)
        )

    def fitness_func(self, instance, solution, solution_idx):
        # Calculate fitness of a solution.
        self.decode_solution(solution)
        items: List[Item] = self.container.items
        left_over: List[Item] = [item for item in self.items if item not in items]

        # Calculate container utilization
        volume_utilization = sum(
            item.length * item.width * item.height for item in items
        ) / (self.container.length * self.container.width * self.container.height)

        # Calculate left over volume non-utilization
        left_over_util = sum(
            item.length * item.width * item.height for item in left_over
        )

        # Calculate priority satisfaction
        priority_score = (
            (
                sum(item.priority * sum(item.position) for item in items)
                / (
                    len(items)
                    * self.container.length
                    * self.container.width
                    * self.container.height
                    * self.max_priority
                )
            )
            if items
            else 0
        )

        # Calculate center of mass satisfaction
        center_mass_score = (
            (
                sum(
                    self.center_mass_score(
                        (
                            self.container.length,
                            self.container.width,
                            self.container.height,
                        ),
                        item,
                    )
                    for item in items
                )
                / (
                    self.container.length
                    * self.container.width
                    * self.container.height
                    * self.container.total_weight
                )
            )
            if items
            else 0
        )

        # Container-specific fitness
        fitness = (
            volume_utilization * 0.5 + center_mass_score * 0.5 + priority_score * 0.1
        ) - (left_over_util)

        return fitness

    def run(self) -> ContainerLoadingSolution:
        # Run the genetic algorithm and return best solution.
        if len(self.items) == 0:
            return {
                "fitness": 0,
                "container": self.container,
                "unused": [],
                # "raw": [],
            }
        self.ga_instance.run()
        solution, solution_fitness, _ = self.ga_instance.best_solution()
        decoded_solution = self.decode_solution(solution)

        # Decode and format the best solution

        result = {
            "fitness": solution_fitness,
            "container": decoded_solution,
            "unused": [item for item in self.items if item not in self.container.items],
        }

        return result


def arrangeContainer(container: Container):
    optimizer = ContainerLoadingGA(container, container.items, False)
    solution = optimizer.run()
    return solution


def arrangePallet(container: Container):
    optimizer = ContainerLoadingGA(container, container.items)
    solution = optimizer.run()
    return solution
