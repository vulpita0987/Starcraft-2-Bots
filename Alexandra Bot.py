from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.data import Difficulty, Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.player import Bot, Computer


class ThreebaseVoidrayBot(BotAI):

    async def on_start(self):
        if 4135 not in self.game_data.abilities:
            gather = self.game_data.abilities.get(
                AbilityId.HARVEST_GATHER.value
            )
            if gather is not None:
                self.game_data.abilities[4135] = gather

        self.relocation_started = False
        self.relocation_complete = False
        self.first_new_nexus_location = None
        self.relocation_worker_tag = None
        self.relocation_build_order_sent = False

        self.voidray_search_index = {}
        self.voidray_defender_tags = set()
        self.large_force_sweep_index = 0

        await self.chat_send("(glhf)")


    async def on_step(self, iteration: int):

        if not self.relocation_complete:
            await self.start_relocation()

            if not self.relocation_complete:
                return

        await self.manage_workers()
        await self.build_gas()
        await self.build_relocated_production()
        await self.produce_probes()
        await self.produce_voidrays()
        self.manage_void_rays()
        await self.manage_supply()


    def get_relocation_location(self):

        if not self.expansion_locations_list:
            return None

        enemy_start = self.enemy_start_locations[0]

        candidates = []

        for location in self.expansion_locations_list:

            own_distance = location.distance_to(
                self.start_location
            )

            enemy_distance = location.distance_to(
                enemy_start
            )

            if own_distance < 20:
                continue

            if own_distance >= enemy_distance:
                continue

            candidates.append(
                (own_distance, location)
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: item[0]
        )

        if len(candidates) >= 3:
            return candidates[2][1]

        return candidates[-1][1]


    async def start_relocation(self):

        target = self.first_new_nexus_location

        if target is None:
            target = self.get_relocation_location()

            if target is None:
                return

            self.first_new_nexus_location = target

        nexuses = self.structures(
            UnitTypeId.NEXUS
        ).closer_than(
            6,
            target
        )

        if nexuses.exists:

            nexus = nexuses.closest_to(target)

            if nexus.is_ready:
                self.relocation_complete = True
                await self.send_all_workers_to_new_base(nexus)
                return

            self.relocation_started = True
            await self.move_workers_to_relocation(target)
            return

        if not self.relocation_started:

            if not self.can_afford(UnitTypeId.NEXUS):
                return

            if not self.workers.exists:
                return

            worker = self.workers.closest_to(target)

            if worker is None:
                return

            self.relocation_worker_tag = worker.tag
            self.relocation_started = True

            worker.move(target)

            await self.move_workers_to_relocation(target)
            return

        worker = self.workers.find_by_tag(
            self.relocation_worker_tag
        )

        if worker is None:
            return

        distance = worker.distance_to(target)

        if distance > 1.5:
            worker.move(target)
            await self.move_workers_to_relocation(target)
            return

        if not self.can_afford(UnitTypeId.NEXUS):
            await self.move_workers_to_relocation(target)
            return

        if not self.relocation_build_order_sent:

            worker.build(
                UnitTypeId.NEXUS,
                target
            )

            self.relocation_build_order_sent = True

        await self.move_workers_to_relocation(target)


    async def move_workers_to_relocation(self, target):

        for worker in self.workers:

            if (
                self.relocation_worker_tag is not None
                and worker.tag == self.relocation_worker_tag
            ):
                continue

            if worker.distance_to(target) > 3:
                worker.move(target)


    async def send_all_workers_to_new_base(self, nexus):

        minerals = self.mineral_field.closer_than(
            12,
            nexus
        )

        if not minerals.exists:
            return

        mineral = minerals.closest_to(nexus)

        for worker in self.workers:
            worker.gather(mineral)


    async def manage_workers(self):

        if self.first_new_nexus_location is None:
            return

        nexuses = self.structures(
            UnitTypeId.NEXUS
        ).closer_than(
            8,
            self.first_new_nexus_location
        )

        if not nexuses.exists:
            return

        nexus = nexuses.closest_to(
            self.first_new_nexus_location
        )

        if not nexus.is_ready:
            return

        minerals = self.mineral_field.closer_than(
            12,
            nexus
        )

        if not minerals.exists:
            return

        mineral = minerals.closest_to(nexus)

        assimilators = self.structures(
            UnitTypeId.ASSIMILATOR
        ).closer_than(
            10,
            nexus
        ).ready

        gas_workers = set()

        for assimilator in assimilators:

            nearby_workers = self.workers.closer_than(
                2.5,
                assimilator
            )

            for worker in nearby_workers[:3]:
                gas_workers.add(worker.tag)

        for worker in self.workers:

            if worker.tag in gas_workers:
                continue

            if worker.distance_to(mineral) > 15:
                worker.gather(mineral)


    async def build_gas(self):

        if not self.relocation_complete:
            return

        if self.first_new_nexus_location is None:
            return

        nexuses = self.structures(
            UnitTypeId.NEXUS
        ).closer_than(
            8,
            self.first_new_nexus_location
        )

        if not nexuses.exists:
            return

        nexus = nexuses.closest_to(
            self.first_new_nexus_location
        )

        if not nexus.is_ready:
            return

        geysers = self.vespene_geyser.closer_than(
            10,
            nexus
        )

        if not geysers.exists:
            return

        assimilators = self.structures(
            UnitTypeId.ASSIMILATOR
        ).closer_than(
            10,
            nexus
        )

        for geyser in geysers:

            if assimilators.closer_than(
                1.5,
                geyser
            ).exists:
                continue

            if not self.can_afford(
                UnitTypeId.ASSIMILATOR
            ):
                return

            workers = self.workers.closer_than(
                10,
                nexus
            )

            if not workers.exists:
                return

            worker = workers.closest_to(
                geyser
            )

            if worker is None:
                return

            worker.build_gas(geyser)

            return


    async def build_relocated_production(self):

        if not self.relocation_complete:
            return

        nexuses = self.structures(
            UnitTypeId.NEXUS
        ).closer_than(
            8,
            self.first_new_nexus_location
        )

        if not nexuses.exists:
            return

        nexus = nexuses.closest_to(
            self.first_new_nexus_location
        )

        if not nexus.is_ready:
            return

        pylons = self.structures(
            UnitTypeId.PYLON
        ).closer_than(
            10,
            nexus
        )

        if not pylons.exists:

            if not self.can_afford(
                UnitTypeId.PYLON
            ):
                return

            worker = self.workers.closest_to(nexus)

            if worker is None:
                return

            await self.build(
                UnitTypeId.PYLON,
                near=nexus,
                build_worker=worker
            )

            return

        ready_pylons = pylons.ready

        if not ready_pylons.exists:
            return

        pylon = ready_pylons.closest_to(nexus)

        gateways = self.structures(
            UnitTypeId.GATEWAY
        ).closer_than(
            12,
            nexus
        )

        if not gateways.exists:

            if not self.can_afford(
                UnitTypeId.GATEWAY
            ):
                return

            worker = self.workers.closest_to(pylon)

            if worker is None:
                return

            await self.build(
                UnitTypeId.GATEWAY,
                near=pylon,
                build_worker=worker
            )

            return

        if not gateways.ready.exists:
            return

        cybercores = self.structures(
            UnitTypeId.CYBERNETICSCORE
        ).closer_than(
            12,
            nexus
        )

        if not cybercores.exists:

            if not self.can_afford(
                UnitTypeId.CYBERNETICSCORE
            ):
                return

            worker = self.workers.closest_to(pylon)

            if worker is None:
                return

            await self.build(
                UnitTypeId.CYBERNETICSCORE,
                near=pylon,
                build_worker=worker
            )

            return

        if not cybercores.ready.exists:
            return

        stargates = self.structures(
            UnitTypeId.STARGATE
        ).closer_than(
            15,
            nexus
        )

        if not stargates.exists:

            if not self.can_afford(
                UnitTypeId.STARGATE
            ):
                return

            worker = self.workers.closest_to(pylon)

            if worker is None:
                return

            await self.build(
                UnitTypeId.STARGATE,
                near=pylon,
                build_worker=worker
            )


    async def produce_probes(self):

        if not self.relocation_complete:
            return

        nexuses = self.structures(
            UnitTypeId.NEXUS
        ).ready

        if not nexuses.exists:
            return

        if self.supply_workers >= (
            nexuses.amount * 22
        ):
            return

        for nexus in nexuses:

            if self.can_afford(
                UnitTypeId.PROBE
            ):
                nexus.train(
                    UnitTypeId.PROBE
                )


    async def produce_voidrays(self):

        stargates = self.structures(
            UnitTypeId.STARGATE
        ).ready

        if not stargates.exists:
            return

        for stargate in stargates:

            if self.can_afford(
                UnitTypeId.VOIDRAY
            ):
                stargate.train(
                    UnitTypeId.VOIDRAY
                )


    def get_voidray_search_locations(self):

        locations = list(
            self.expansion_locations_list
        )

        enemy_start = self.enemy_start_locations[0]

        if not any(
            location.distance_to(enemy_start) < 1
            for location in locations
        ):
            locations.append(enemy_start)

        locations.sort(
            key=lambda location:
                location.distance_to(enemy_start)
        )

        return locations


    def manage_void_rays(self):

        voidrays = self.units(
            UnitTypeId.VOIDRAY
        )

        if not voidrays.exists:
            return

        search_locations = (
            self.get_voidray_search_locations()
        )

        if not search_locations:
            return

        if voidrays.amount > 15:
            self.manage_large_voidray_force(
                voidrays
            )
            return

        for voidray in voidrays:

            if voidray.tag not in self.voidray_search_index:
                self.voidray_search_index[
                    voidray.tag
                ] = (
                    voidray.tag % len(search_locations)
                )

            index = self.voidray_search_index[
                voidray.tag
            ]

            target_location = search_locations[index]

            threats = self.enemy_units.filter(
                lambda enemy:
                    enemy.can_be_attacked
                    and enemy.can_attack_air
            )

            if threats.exists:

                voidray.attack(
                    threats.closest_to(voidray)
                )

                continue

            enemy_units = self.enemy_units.filter(
                lambda enemy:
                    enemy.can_be_attacked
            )

            if enemy_units.exists:

                voidray.attack(
                    enemy_units.closest_to(voidray)
                )

                continue

            enemy_structures = self.enemy_structures.filter(
                lambda enemy:
                    enemy.can_be_attacked
            )

            if enemy_structures.exists:

                voidray.attack(
                    enemy_structures.closest_to(voidray)
                )

                continue

            if voidray.distance_to(
                target_location
            ) > 8:

                voidray.move(
                    target_location
                )

                continue

            self.voidray_search_index[
                voidray.tag
            ] = (
                index + 1
            ) % len(search_locations)


    def manage_large_voidray_force(self, voidrays):

        if not self.townhalls.ready.exists:
            return

        defense_base = self.townhalls.ready.closest_to(
            self.start_location
        )

        defense_point = defense_base.position

        living_tags = {
            voidray.tag
            for voidray in voidrays
        }

        self.voidray_defender_tags.intersection_update(
            living_tags
        )

        defenders_needed = (
            5 - len(self.voidray_defender_tags)
        )

        if defenders_needed > 0:

            available_voidrays = sorted(
                (
                    voidray
                    for voidray in voidrays
                    if voidray.tag
                    not in self.voidray_defender_tags
                ),
                key=lambda voidray:
                    voidray.distance_to(
                        defense_point
                    )
            )

            self.voidray_defender_tags.update(
                voidray.tag
                for voidray in available_voidrays[
                    :defenders_needed
                ]
            )

        defenders = [
            voidray
            for voidray in voidrays
            if voidray.tag
            in self.voidray_defender_tags
        ]

        attackers = [
            voidray
            for voidray in voidrays
            if voidray.tag
            not in self.voidray_defender_tags
        ]

        visible_threats = self.enemy_units.filter(
            lambda enemy:
                enemy.can_be_attacked
                and enemy.distance_to(
                    defense_point
                ) < 35
        )

        for defender in defenders:

            if visible_threats.exists:
                defender.attack(
                    visible_threats.closest_to(
                        defender
                    )
                )
            else:
                defender.move(
                    defense_point
                )

        base_sites = list(
            self.expansion_locations_list
        )

        enemy_main = self.enemy_start_locations[0]

        if not any(
            site.distance_to(enemy_main) < 1
            for site in base_sites
        ):
            base_sites.append(enemy_main)

        if not attackers or not base_sites:
            return

        target = base_sites[
            self.large_force_sweep_index
        ]

        if all(
            attacker.distance_to(target) < 10
            for attacker in attackers
        ):

            self.large_force_sweep_index = (
                self.large_force_sweep_index + 1
            ) % len(base_sites)

            target = base_sites[
                self.large_force_sweep_index
            ]

        targets = self.enemy_units.filter(
            lambda enemy:
                enemy.can_be_attacked
        )

        if targets.exists:

            for attacker in attackers:
                attacker.attack(
                    targets.closest_to(attacker)
                )

        else:

            for attacker in attackers:
                attacker.move(target)


    async def manage_supply(self):

        if self.supply_left >= 4:
            return

        if not self.can_afford(
            UnitTypeId.PYLON
        ):
            return

        nexuses = self.structures(
            UnitTypeId.NEXUS
        ).closer_than(
            10,
            self.first_new_nexus_location
        )

        if not nexuses.exists:
            return

        nexus = nexuses.closest_to(
            self.first_new_nexus_location
        )

        worker = self.workers.closest_to(nexus)

        if worker is None:
            return

        await self.build(
            UnitTypeId.PYLON,
            near=nexus,
            build_worker=worker
        )


SimpleProtossBot = ThreebaseVoidrayBot


def main():

    run_game(
        maps.get("(2)CatalystLE"),
        [
            Bot(
                Race.Protoss,
                ThreebaseVoidrayBot(),
            ),
            Computer(
                Race.Protoss,
                Difficulty.Easy,
            ),
        ],
        realtime=False,
    )


if __name__ == "__main__":
    main()