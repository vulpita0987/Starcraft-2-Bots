
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

     self.expansion_worker = None
     self.expansion_target = None
     self.expansion_in_progress = False

     self.second_nexus_started = False
     
     
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

    async def build_workers(self):

     for nexus in self.townhalls.ready:

        workers = self.workers.closer_than(
            10,
            nexus
        )

        if (
            workers.amount < 22
            and nexus.is_idle
            and self.can_afford(U.PROBE)
        ):
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
     if not self.relocation_complete:
        return

     if self.first_new_nexus_location is None:
        return
     
     nexuses = self.structures(U.NEXUS).closer_than(
        5,
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
        nexus.position
     )

     if not geysers.exists:
        return

     assimilators = self.structures(
        U.ASSIMILATOR
     ).closer_than(
        10,
        nexus.position
     )

     for geyser in geysers:

        if assimilators.closer_than(
            1.5,
            geyser.position
        ).exists:
            continue

        # Need 75 minerals
        if not self.can_afford(U.ASSIMILATOR):
            return

        workers = self.workers.closer_than(
            10,
            nexus.position
        )

        if not workers.exists:
            return

        if workers.idle.exists:
            worker = workers.idle.closest_to(
                geyser.position
            )
        else:
            worker = workers.closest_to(
                geyser.position
            )

        print("BUILDING ASSIMILATOR")
        print("Worker:", worker.tag)
        print("Geyser position:", geyser.position)

        await self.build(
            U.ASSIMILATOR,
            near=geyser,
            build_worker=worker
        )

        print("ASSIMILATOR BUILD ORDER SENT")

        return




    async def build_forge(self):

     nexus = self.townhalls.closest_to(
        self.first_new_nexus_location
     )

     if not nexus.is_ready:
        return

     if (
        self.can_afford(U.FORGE)
        and self.structures(U.FORGE).amount < 1
        and not self.already_pending(U.FORGE)
     ):

        await self.build(
            U.FORGE,
            near=nexus
        )

    async def build_cannons(self):

     nexus = self.townhalls.closest_to(
        self.first_new_nexus_location
     )
     location = nexus.position.towards(self.start_location, 8)
     location1 = nexus.position.towards(self.start_location, 8)

     if nexus.is_ready and self.structures(U.FORGE).ready.amount and self.structures(U.PHOTONCANNON).amount < 4 and self.can_afford(U.PHOTONCANNON) and self.structures(U.PHOTONCANNON).filter(lambda cannon: not cannon.is_ready).amount < 4:
        await self.build(U.PHOTONCANNON, near=location)

     if nexus.is_ready and self.structures(U.FORGE).ready.amount and self.structures(U.PHOTONCANNON).amount < 4 and self.can_afford(U.PHOTONCANNON) and self.structures(U.PHOTONCANNON).filter(lambda cannon: not cannon.is_ready).amount < 4:
             await self.build(U.PHOTONCANNON, near=location1)

    async def build_carrier_tech(self):

     nexus = self.townhalls.closest_to(
        self.first_new_nexus_location
     )

     if not nexus.is_ready:
        return

     if not self.structures(U.GATEWAY).exists:
        building = U.GATEWAY

     elif not self.structures(U.GATEWAY).ready.exists:
        return

     elif not self.structures(U.CYBERNETICSCORE).exists:
        building = U.CYBERNETICSCORE

     elif not self.structures(U.CYBERNETICSCORE).ready.exists:
        return

     elif not self.structures(U.STARGATE).exists:
        building = U.STARGATE

     elif not self.structures(U.STARGATE).ready.exists:
        return

     elif not self.structures(U.FLEETBEACON).exists:
        building = U.FLEETBEACON

     else:
        return


     if not self.can_afford(building):
        return

     if self.already_pending(building):
        return


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
            building,
            near=position
        )

        return

    async def manage_carriers(self):
    
         if self.structures(U.STARGATE).ready.exists:
            for sg in self.structures(U.STARGATE).ready:
                if (
                    sg.is_idle
                    and self.can_afford(U.CARRIER)
                    and self.supply_left >= 6
                ):
                    sg.train(U.CARRIER)
    
         carriers = self.units(U.CARRIER)
    
         if not carriers:
            return
    
         if not hasattr(self, "carrier_locations"):
            self.carrier_locations = list(self.expansion_locations_list)
    
         if not hasattr(self, "carrier_targets"):
            self.carrier_targets = {}
    
         for carrier in carriers:
    
            if carrier.tag not in self.carrier_targets:
                self.carrier_targets[carrier.tag] = 0
    
            index = self.carrier_targets[carrier.tag]
            target_location = self.carrier_locations[index]
    
            nearby = self.enemy_structures.closer_than(
                20,
                target_location
            )
    
            if nearby.exists:
    
                target = nearby.closest_to(carrier)
    
                carrier.attack(target)
    
            else:
    
                # Fly to expansion
                if carrier.distance_to(target_location) > 8:
                    carrier.attack(target_location)
    
                else:
                    # Expansion cleared
                    index += 1
    
                    if index >= len(self.carrier_locations):
                        index = 0
    
                    self.carrier_targets[carrier.tag] = index

    async def manage_carriers(self):

     print("===============================")
     print("CARRIER FUNCTION START")
     print("===============================")


     stargates = self.structures(U.STARGATE).ready

     print("Stargates:", stargates.amount)

     for sg in stargates:

        if (
            sg.is_idle
            and self.can_afford(U.CARRIER)
            and self.supply_left >= 6
        ):
            print("BUILDING CARRIER")
            sg.train(U.CARRIER)


     carriers = self.units(U.CARRIER)

     print("Carriers:", carriers.amount)

     if not carriers.exists:
        return


     if not hasattr(self, "carrier_locations"):

        self.carrier_locations = list(
            self.expansion_locations_list
        )

        print(
            "Carrier locations:",
            len(self.carrier_locations)
        )


     if not hasattr(self, "carrier_targets"):
        self.carrier_targets = {}

     for carrier in carriers:

        print("-------------------------------")
        print("Controlling Carrier:", carrier.tag)


        if carrier.tag not in self.carrier_targets:

            self.carrier_targets[carrier.tag] = 0

            print(
                "New carrier - starting at location 0"
            )

        index = self.carrier_targets[carrier.tag]

        target_location = self.carrier_locations[index]

        print("Current target index:", index)
        print("Current target:", target_location)


        nearby_units = self.enemy_units.closer_than(
            20,
            target_location
        )

        nearby_structures = self.enemy_structures.closer_than(
            20,
            target_location
        )

        print(
            "Enemy units:",
            nearby_units.amount
        )

        print(
            "Enemy structures:",
            nearby_structures.amount
        )


        if nearby_units.exists:

            target = nearby_units.closest_to(carrier)

            print(
                "ENEMY UNIT FOUND - ATTACKING:",
                target
            )

            carrier.attack(target)

            continue

        if nearby_structures.exists:

            target = nearby_structures.closest_to(carrier)

            print(
                "ENEMY STRUCTURE FOUND - ATTACKING:",
                target
            )

            carrier.attack(target)

            continue


        print("No enemy detected at this location.")


        if carrier.distance_to(target_location) <= 8:

            print(
                "LOCATION CLEARED - MOVING TO NEXT LOCATION"
            )

            index += 1

            if index >= len(self.carrier_locations):

                index = 0

                print(
                    "Reached end of map search - restarting"
                )

            self.carrier_targets[carrier.tag] = index

            print(
                "New target index:",
                index
            )

            continue

        print(
            "Travelling to:",
            target_location
        )

        carrier.move(target_location)

    
    async def manage_expansions(self):

     print("1 - entered manage_expansions")

     if self.second_nexus_started:
        print("2 - second Nexus already started")
        return

     print("3 - checking minerals")

     if not self.can_afford(U.NEXUS):
        print("4 - cannot afford Nexus")
        return

     print("5 - can afford Nexus")

     if not self.workers.idle.exists:
        print("6 - NO IDLE WORKERS")
        return

     print("7 - idle worker exists")

     worker = self.workers.idle.random

     print("8 - selected worker:", worker.tag)

     expansions = [
        location
        for location in self.expansion_locations_list
        if not self.structures(U.NEXUS).closer_than(5, location).exists
     ]

     if not expansions:
        print("9 - NO AVAILABLE EXPANSION LOCATION")
        return

     expansion_location = expansions[0]

     print("10 - expansion location:", expansion_location)

     print("11 - BUILDING NEXUS")

     await self.build(
        U.NEXUS,
        near=expansion_location,
        build_worker=worker
     )

     self.second_nexus_started = True

     print("12 - NEXUS BUILD ORDER SENT")


     
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
     await self.build_cannons()
     await self.build_carrier_tech()
     await self.manage_carriers()

     await self.manage_expansions()
     
     


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