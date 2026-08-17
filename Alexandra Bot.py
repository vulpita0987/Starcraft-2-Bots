
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
import random


map_path = maps.get("AbyssalReefLE")


class SimpleProtossBot(BotAI):

   
  
    
    def __init__(self):
     super().__init__()
     self.expansion_number1 = random.randint(4, 8)
     self.relocation_complete = False
     self.first_new_nexus_location = None
     
    async def start_relocation(self):

     expansion_number = self.expansion_number1

     expansions = sorted(
        self.expansion_locations_list,
        key=lambda p: p.distance_to(self.start_location)
     )

     location = expansions[expansion_number]

     nexus = self.structures(U.NEXUS).closer_than(
        5,
        location
     )

     if nexus.exists:

        nexus = nexus.closest_to(location)

        if nexus.is_ready:
            self.relocation_complete = True
            self.first_new_nexus_location = location
            return

     if not self.can_afford(U.NEXUS):
        return

     for worker in self.workers:
        worker.move(location)

     worker = self.workers.random

     if worker.distance_to(location) > 3:
        worker.move(location)
        return

     await self.build(
        U.NEXUS,
        near=location,
        build_worker=worker
     )

    async def manage_workers(self): # needs looking into

     for nexus in self.townhalls.ready:

        workers = self.workers.closer_than(10, nexus)

        assimilators = self.structures(U.ASSIMILATOR).closer_than(
            10,
            nexus
        ).ready

        minerals = self.mineral_field.closer_than(
            10,
            nexus
        )

        for worker in workers:

            if not worker.is_idle:
                continue

            gas_target = None

            for assimilator in assimilators:

                if assimilator.assigned_harvesters < 3:
                    gas_target = assimilator
                    break

            if gas_target is not None:
                worker.gather(gas_target)
                continue

            if minerals.exists:
                mineral = minerals.closest_to(worker)
                worker.gather(mineral)

    async def build_workers(self): #needs looking into

     nexus = self.townhalls.closest_to(self.first_new_nexus_location)

     workers = self.workers.closer_than(10, nexus)

     if workers.amount < 22 and nexus.is_idle and self.can_afford(U.PROBE):
        nexus.train(U.PROBE)

    async def build_pylons(self):

     if self.supply_left > 5:
        return

     if not self.can_afford(U.PYLON):
        return

     if self.already_pending(U.PYLON):
        return

     nexus = self.townhalls.closest_to(
        self.first_new_nexus_location
     )

     for i in range(20):

        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(5, 10)

        position = Point2((
            nexus.position.x + math.cos(angle) * distance,
            nexus.position.y + math.sin(angle) * distance
        ))

        buildings = self.structures.closer_than(
            5,
            position
        )

        if buildings.exists:
            continue

        if not self.in_pathing_grid(position):
            continue

        await self.build(
            U.PYLON,
            near=position
        )

        return
    
    async def build_gas(self):

     nexus = self.townhalls.closest_to(
        self.first_new_nexus_location
     )

     if not nexus.is_ready:
        return

     geysers = self.vespene_geyser.closer_than(
        10,
        nexus
     )

     for geyser in geysers:

        assimilators = self.structures(U.ASSIMILATOR).closer_than(
            1.5,
            geyser
        )

        if assimilators.exists:
            continue

        if not self.can_afford(U.ASSIMILATOR):
            return

        worker = self.workers.closest_to(geyser)

        await self.build(
            U.ASSIMILATOR,
            near=geyser,
            build_worker=worker
        ) 

    async def build_forge(self):

     nexus = self.townhalls.closest_to(
        self.first_new_nexus_location
     )

     if not nexus.is_ready:
        return

     if self.can_afford(U.FORGE):

        await self.build(
            U.FORGE,
            near=nexus
        )

#Next:

#Gateway

#Cybernetics Core

#Stargate

#Fleet Beacon

#Carriers

    # ---------- MAIN LOOP ----------

    
  
    async def on_step(self, iteration: int):

     if self.relocation_complete == False:
        await self.start_relocation()

     if not self.relocation_complete:
        return
     await self.manage_workers()
     await self.build_workers()
     await self.build_pylons()
     await self.build_gas()
     await self.build_forge()
     
     


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

#Forge
#Nexus
#  │
#  └── Gateway
#        │
#        └── Cybernetics Core
#              │
#              ├── Twilight Council
#              │      ├── Templar Archives
#              │      └── Dark Shrine
#              │
#              ├── Robotics Facility
#              │      └── Robotics Bay
#              │
#              └── Stargate
#                     │
#                     └── Fleet Beacon

#Gateway / Warp Gate

#Zealot
#Adept
#Stalker
#Sentry

#Robotics Facility

#Observer
#Immortal
#Warp Prism

#Robotics Bay

#Colossus
#Disruptor

#Stargate

#Phoenix
#Oracle
#Void Ray
#Carrier
#Tempest

#Templar Archives

#High Templar
#Archon

#Dark Shrine

#Dark Templar

#Fleet Beacon

#Mothership and higher Stargate technology