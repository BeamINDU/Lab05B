from typing import Optional, Union
from app import schemas, models

from abc import ABC, abstractmethod


class PackageAbstractFactory(ABC):
    """Abstract factory for creating container-related models."""

    @abstractmethod
    def create_base(self, data: dict) -> schemas.PackageBase:
        pass

    @abstractmethod
    def create_create_model(self, data: dict) -> schemas.PackageCreate:
        pass

    @abstractmethod
    def create_update_model(
        self, data: dict, baseData: Optional[dict] = None
    ) -> schemas.PackageUpdate:
        pass


class ShipContainerFactory(PackageAbstractFactory):
    def check_valid_size(
        self,
        container: schemas.ShipContainerBase,
        baseContainer: Optional[dict] = None,
    ):
        w, l, h, lw, ll, lh = (
            (
                baseContainer.get("package_width"),
                baseContainer.get("package_length"),
                baseContainer.get("package_height"),
                baseContainer.get("load_width"),
                baseContainer.get("load_length"),
                baseContainer.get("load_height"),
            )
            if baseContainer
            else (
                None,
                None,
                None,
                None,
                None,
                None,
            )
        )

        return (
            (container.package_height or h) < (container.load_height or lh)
            or (container.package_width or w) < (container.load_width or lw)
            or (container.package_length or l) < (container.load_length or ll)
        )

    def create_base(self, data: dict) -> schemas.ShipContainerBase:
        container = schemas.ShipContainerBase(**data)
        if self.check_valid_size(container):
            raise ValueError("container size must be more than load size.")
        return container

    def create_create_model(self, data: dict) -> schemas.ShipContainerCreate:
        container = schemas.ShipContainerCreate(**data)
        if self.check_valid_size(container):
            raise ValueError("container size must be more than load size.")
        return container

    def create_update_model(
        self, data: dict, baseData: dict
    ) -> schemas.ShipContainerUpdate:
        container = schemas.ShipContainerUpdate(**data)
        if self.check_valid_size(container, baseData):
            raise ValueError("container size must be more than load size.")
        return container


class CartonContainerFactory(PackageAbstractFactory):
    def check_valid_size(
        self,
        container: schemas.CartonBase,
        baseContainer: Optional[dict] = None,
    ):
        w, l, h, lw, ll, lh = (
            (
                baseContainer.get("package_width"),
                baseContainer.get("package_length"),
                baseContainer.get("package_height"),
                baseContainer.get("load_width"),
                baseContainer.get("load_length"),
                baseContainer.get("load_height"),
            )
            if baseContainer
            else (
                None,
                None,
                None,
                None,
                None,
                None,
            )
        )

        return (
            (container.package_height or h) < (container.load_height or lh)
            or (container.package_width or w) < (container.load_width or lw)
            or (container.package_length or l) < (container.load_length or ll)
        )

    def create_base(self, data: dict) -> schemas.CartonBase:
        container = schemas.CartonBase(**data)
        if self.check_valid_size(container):
            raise ValueError("container size must be more than load size.")
        return container

    def create_create_model(self, data: dict) -> schemas.CartonCreate:
        container = schemas.CartonCreate(**data)
        if self.check_valid_size(container):
            raise ValueError("container size must be more than load size.")
        return container

    def create_update_model(self, data: dict, baseData: dict) -> schemas.CartonUpdate:
        container = schemas.CartonUpdate(**data)
        if self.check_valid_size(container, baseData):
            raise ValueError("container size must be more than load size.")
        return container


class PalletContainerFactory(PackageAbstractFactory):
    def create_base(self, data: dict) -> schemas.PalletBase:
        return schemas.PalletBase(**data)

    def create_create_model(self, data: dict) -> schemas.PalletCreate:
        return schemas.PalletCreate(**data)

    def create_update_model(self, data: dict) -> schemas.PalletUpdate:
        return schemas.PalletUpdate(**data)


class PackageFactory:
    """Factory to get the right Abstract Factory based on container type."""

    _factories = {
        models.PackageType.container: ShipContainerFactory(),
        models.PackageType.pallet: PalletContainerFactory(),
        models.PackageType.carton: CartonContainerFactory(),
    }

    @classmethod
    def get_factory(cls, container_type: models.PackageType) -> PackageAbstractFactory:
        factory = cls._factories.get(container_type)
        if not factory:
            raise ValueError(f"No factory for type: {container_type}")
        return factory
