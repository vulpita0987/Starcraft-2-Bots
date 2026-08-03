#Core bot and run loop
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
       
    async def manage_workers(self):

    # ==========================================================
    # Train probes until each Nexus is fully saturated
    # (16 mineral + 6 gas = 22 workers per base)
    # ==========================================================

     ideal_workers = self.townhalls.amount * 22

     for nexus in self.townhalls.ready.idle:

        if (
            self.workers.amount < ideal_workers
            and self.can_afford(U.PROBE)
        ):
            nexus.train(U.PROBE)

    # ==========================================================
    # Choose one worker to become the expansion worker
    # ==========================================================

     if self.expansion_worker_tag is None:

        if self.workers.gathering.exists:

            worker = self.workers.gathering.random

            self.expansion_worker_tag = worker.tag
            self.expansion_location = self.get_far_expansion()

    # ==========================================================
    # Control the expansion worker
    # ==========================================================

     worker = self.workers.find_by_tag(self.expansion_worker_tag)
 
     if (
        worker is not None
        and self.expansion_location is not None
        and not self.second_nexus_started
     ):

        # Wait until five cannons are completed
        if self.structures(U.PHOTONCANNON).ready.amount < 5:

            if worker.distance_to(self.expansion_location) > 3:
                worker.move(self.expansion_location)

        else:

            # Build the second Nexus
            if self.can_afford(U.NEXUS):

                worker.build(U.NEXUS, self.expansion_location)
                self.second_nexus_started = True

    # ==========================================================
    # Make sure no worker stays idle
    # ==========================================================
 
     for worker in self.workers.idle:

        # Fill gas first
        gas = self.structures(U.ASSIMILATOR).ready.filter(
            lambda a: a.assigned_harvesters < a.ideal_harvesters
        )

        if gas.exists:

            worker.gather(gas.first)

        else:

            # Otherwise mine minerals
            nexus = self.townhalls.ready.closest_to(worker)

            mineral = self.mineral_field.closest_to(nexus)

            worker.gather(mineral)

    def get_far_expansion(self):
     """Returns the expansion two bases away from the starting location."""

     expansions = sorted(
        self.expansion_locations_list,
        key=lambda p: p.distance_to(self.start_location)
     )

     if len(expansions) >= 3:
        return expansions[2]

     return expansions[1]

    
    async def build_pylons(self):

    # ==========================================================
    # First pylon at every Nexus
    # ==========================================================

     for nexus in self.townhalls.ready:

        nearby = self.structures(U.PYLON).closer_than(20, nexus)

        if (
            nearby.amount == 0
            and self.can_afford(U.PYLON)
            and not self.already_pending(U.PYLON)
        ):

            await self.build(
                U.PYLON,
                near=self.get_pylon_position(nexus)
            )

            return

    # ==========================================================
    # Build extra pylons when supply gets low
    # ==========================================================

     if (
        self.supply_left < 8
        and self.can_afford(U.PYLON)
        and self.already_pending(U.PYLON) == 0
     ):

        nexus = self.townhalls.ready.random

        await self.build(
            U.PYLON,
            near=nexus.position.towards(
                self.game_info.map_center,
                8
            ),
            placement_step=2
        )

    def get_pylon_position(self, nexus):

    # Position slightly inside your base from the top of the ramp
     return self.main_base_ramp.top_center.towards(
        self.start_location,
        4
     )

    # ---------- MAIN LOOP ----------

    async def on_step(self, iteration: int):

        await self.manage_workers()
        await self.build_pylons()
        await self.manage_buildings()
        #  await self.build_choke_cannons()
      #  await self.build_assimilators_safe()
     
      
     #   await self.manage_zealots()
    
      #  await self.manage_carriers()
     
       

        
        


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
