
from sc2.bot_ai import BotAI
from sc2.main import run_game

#Game setup
from sc2.data import Race, Difficulty
from sc2.player import Bot, Computer
from sc2 import maps
from pathlib import Path

#Units, structures, and abilities
from sc2.ids.unit_typeid import UnitTypeId as U
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.upgrade_id import UpgradeId

#Positioning & geometry
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

#Events and game state
from sc2.game_info import GameInfo
from sc2.game_state import GameState

import math

map_path = maps.get("AbyssalReefLE")


class SimpleProtossBot(BotAI):

   
  
    
    def __init__(self):
     super().__init__()

     self.expansion_worker_tag = None
     self.expansion_location = None
     self.second_nexus_started = False

     self.relocation_started = False
     self.relocation_worker_tag = None
     self.relocation_location = None
     self.relocation_workers_sent = False
     self.relocation_complete = False

     self.worker_target = 22

     self.gas_build_started = False

    async def start_relocation(self):

     if self.relocation_complete:
        return

     if self.relocation_location is None:

        expansions = sorted(
            self.expansion_locations_list,
            key=lambda p: p.distance_to(self.start_location)
        )

        if len(expansions) < 3:
            return

        self.relocation_location = expansions[4]

     if not self.relocation_started:

        if not self.can_afford(U.NEXUS):
            return

        if self.relocation_worker_tag is None:

            if not self.workers.gathering.exists:
                return

            worker = self.workers.gathering.random

            self.relocation_worker_tag = worker.tag

        worker = self.workers.find_by_tag(
            self.relocation_worker_tag
        )

        if worker is None:
            self.relocation_worker_tag = None
            return

        if worker.distance_to(self.relocation_location) > 3:

            worker.move(self.relocation_location)

            return

        await self.build(
            U.NEXUS,
            near=self.relocation_location,
            build_worker=worker
        )

        self.relocation_started = True

        return

     if not self.relocation_workers_sent:

        for worker in self.workers:

            worker.move(self.relocation_location)

        self.relocation_workers_sent = True

     nexus = self.structures(U.NEXUS).closer_than(
        5,
        self.relocation_location
     )

     if not nexus.exists:
        return

     new_nexus = nexus.closest_to(
        self.relocation_location
     )

     if not new_nexus.is_ready:
        return

     minerals = self.mineral_field.closest_to(
        new_nexus
     )

     if not minerals:
        return

     for worker in self.workers:

        worker.gather(minerals)

     self.relocation_complete = True


    async def build_workers(self):

     if not self.relocation_complete:
        return

     if self.workers.amount >= 22:
        return

     if self.relocation_location is None:
        return

     nexuses = self.structures(U.NEXUS).closer_than(
        5,
        self.relocation_location
     )

     if not nexuses.exists:
        return

     nexus = nexuses.closest_to(
        self.relocation_location
     )

     if not nexus.is_ready:
        return

     if (
        self.can_afford(U.PROBE)
        and self.supply_left > 0
        and not self.already_pending(U.PROBE)
     ):

        nexus.train(U.PROBE)
    
    async def manage_workers_and_gas(self):

     if not self.relocation_complete:
        return

     if self.relocation_location is None:
        return

     nexuses = self.structures(U.NEXUS).closer_than(
        5,
        self.relocation_location
     )

     if not nexuses.exists:
        return

     nexus = nexuses.closest_to(
        self.relocation_location
     )

     if not nexus.is_ready:
        return

     geysers = self.vespene_geyser.closer_than(
        10,
        nexus
     )

     if not geysers.exists:
        return

     assimilators = self.structures(U.ASSIMILATOR).closer_than(
        10,
        nexus
     )

     for geyser in geysers:

        if assimilators.closer_than(1.5, geyser).exists:
            continue

        if not self.can_afford(U.ASSIMILATOR):
            break

        available_workers = self.workers.idle

        if not available_workers.exists:
            break

        worker = available_workers.closest_to(
            geyser
        )

        # Build the Assimilator.
        await self.build(
            U.ASSIMILATOR,
            near=geyser,
            build_worker=worker
        )
        return

     assimilators = self.structures(U.ASSIMILATOR).closer_than(
        10,
        nexus
     )

     for assimilator in assimilators.ready:

        while (
            assimilator.assigned_harvesters < 3
            and self.workers.idle.exists
        ):

            worker = self.workers.idle.closest_to(
                assimilator
            )

            worker.gather(
                assimilator
            )

     minerals = self.mineral_field.closer_than(
        10,
        nexus
     )

     if not minerals.exists:
        return

     mineral_patch = minerals.closest_to(
        nexus
     )

     for worker in self.workers.idle:

        worker.gather(
            mineral_patch
        )

    async def build_workers(self):

     if not self.relocation_complete:
        return

     if self.relocation_location is None:
        return

     nexuses = self.structures(U.NEXUS).closer_than(
        5,
        self.relocation_location
     )

     if not nexuses.exists:
        return

     nexus = nexuses.closest_to(
        self.relocation_location
     )
 
     if not nexus.is_ready:
        return

     if self.workers.amount >= self.worker_target:
        return
 
     if (
        nexus.is_idle
        and self.can_afford(U.PROBE)
        and self.supply_left > 0
     ):
        nexus.train(U.PROBE)

    async def build_gas(self):

     if not self.relocation_complete:
        return

     if self.relocation_location is None:
        return

     nexuses = self.structures(U.NEXUS).closer_than(
        5,
        self.relocation_location
     )

     if not nexuses.exists:
        return

     nexus = nexuses.closest_to(
        self.relocation_location
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
        U.ASSIMILATOR
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

        if not self.can_afford(U.ASSIMILATOR):
            return

        workers = self.workers.closer_than(
            10,
            nexus
        )

        if not workers.exists:
            return

        idle_workers = workers.idle

        if idle_workers.exists:

            worker = idle_workers.closest_to(
                geyser
            )
        else:
            worker = workers.closest_to(
                geyser
            )

        await self.build(
            U.ASSIMILATOR,
            near=geyser,
            build_worker=worker
        )
        return


    async def manage_workers(self):

     if not self.relocation_complete:
        return

     if self.relocation_location is None:
        return

     nexuses = self.structures(U.NEXUS).closer_than(
        5,
        self.relocation_location
     )

     if not nexuses.exists:
        return

     nexus = nexuses.closest_to(
        self.relocation_location
     )

     if not nexus.is_ready:
        return

     assimilators = self.structures(
        U.ASSIMILATOR
     ).closer_than(
        10,
        nexus
     ).ready

     gas_workers_needed = 0

     for assimilator in assimilators:

        if assimilator.assigned_harvesters < 3:

            gas_workers_needed += (
                3 - assimilator.assigned_harvesters
            )

     if gas_workers_needed > 0:

        candidates = self.workers.filter(
            lambda worker:
                worker.is_gathering
                and worker.distance_to(nexus) < 10
        )

        for worker in candidates:

            if gas_workers_needed <= 0:
                break
            target_gas = None

            for assimilator in assimilators:

                if assimilator.assigned_harvesters < 3:
                    target_gas = assimilator
                    break

            if target_gas is None:
                break

            worker.gather(target_gas)

            gas_workers_needed -= 1

     for worker in self.workers.idle:

        target_gas = None

        for assimilator in assimilators:

            if assimilator.assigned_harvesters < 3:
                target_gas = assimilator
                break

        if target_gas is not None:

            worker.gather(target_gas)
        else:
            break

     minerals = self.mineral_field.closer_than(
        10,
        nexus
     )

     if not minerals.exists:
        return


     for worker in self.workers.idle:

        mineral = minerals.closest_to(
            worker
        )

        worker.gather(mineral)
    # ---------- MAIN LOOP ----------

    
  
    async def on_step(self, iteration: int):

     await self.start_relocation()
     if not self.relocation_complete:
        return
     await self.build_workers()
     await self.build_gas()
     await self.manage_workers()


# Run the game
if __name__ == "__main__":
    run_game(
        map_path,
        [Bot(Race.Protoss, SimpleProtossBot()), Computer(Race.Terran, Difficulty.Easy)],
        realtime=True,
    )

# Structures  instead of Units - for buildings 
# Units for Litlle Moving Things
# =============================================================================
# OWAIN'S COMMENT - SUGGESTED FIX (COMMENTED OUT, SO THIS DOES NOT RUN)
# =============================================================================
# Alexandra's active code above is unchanged. BurnySC2 7 separates mobile units
# from buildings. Pylons and Assimilators therefore need to be checked through
# self.structures instead of self.units. Otherwise the completed Pylon count can
# remain zero and the bot can keep ordering another Pylon.
#
# Suggested replacement for build_initial_pylon:
#
# async def build_initial_pylon(self):
#     if (
#         self.structures(U.PYLON).amount == 0
#         and self.can_afford(U.PYLON)
#         and not self.already_pending(U.PYLON)
#     ):
#         choke = self.main_base_ramp.top_center
#         safe_pos = choke.towards(self.start_location, distance=3)
#         await self.build(U.PYLON, near=safe_pos)
#
# Suggested replacement inside fill_gas:
#
# for assim in self.structures(U.ASSIMILATOR).ready:
#     while (
#         assim.assigned_harvesters < assim.ideal_harvesters
#         and self.workers.idle.exists
#     ):
#         worker = self.workers.idle.random
#         worker.gather(assim)
# =============================================================================
