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

    # ==========================================================
    # Expansion / relocation variables
    # ==========================================================

     self.expansion_worker_tag = None
     self.expansion_location = None
     self.second_nexus_started = False


    # ==========================================================
    # Early relocation experiment
    # ==========================================================

     self.relocation_started = False
     self.relocation_worker_tag = None
     self.relocation_location = None
     self.relocation_workers_sent = False
     self.relocation_complete = False


    # ==========================================================
    # Worker production
    # ==========================================================

     self.worker_target = 22


    # ==========================================================
    # Gas / Assimilator construction
    # ==========================================================

     self.gas_build_started = False




   
   
    async def start_relocation(self):

    # ==========================================================
    # If relocation is completely finished, do nothing.
    # ==========================================================

     if self.relocation_complete:
        return


    # ==========================================================
    # CHOOSE THE NEW BASE LOCATION
    #
    # Sort all expansion locations by distance from our starting
    # location.
    #
    # expansions[0] = closest expansion
    # expansions[1] = second closest
    # expansions[2] = third closest
    #
    # We want the THIRD location so that the new base is
    # noticeably farther away from our starting base.
    # ==========================================================

     if self.relocation_location is None:

        expansions = sorted(
            self.expansion_locations_list,
            key=lambda p: p.distance_to(self.start_location)
        )

        if len(expansions) < 3:
            return

        self.relocation_location = expansions[4]


    # ==========================================================
    # STEP 1:
    # Wait until we can afford a Nexus.
    # ==========================================================

     if not self.relocation_started:

        if not self.can_afford(U.NEXUS):
            return


        # ======================================================
        # Find ONE worker to build the Nexus.
        # ======================================================

        if self.relocation_worker_tag is None:

            if not self.workers.gathering.exists:
                return

            worker = self.workers.gathering.random

            self.relocation_worker_tag = worker.tag


        # ======================================================
        # Find that worker again.
        # ======================================================

        worker = self.workers.find_by_tag(
            self.relocation_worker_tag
        )

        if worker is None:
            self.relocation_worker_tag = None
            return


        # ======================================================
        # Move the worker to the new base location.
        # ======================================================

        if worker.distance_to(self.relocation_location) > 3:

            worker.move(self.relocation_location)

            return


        # ======================================================
        # Build the Nexus.
        # ======================================================

        await self.build(
            U.NEXUS,
            near=self.relocation_location,
            build_worker=worker
        )

        self.relocation_started = True

        return


    # ==========================================================
    # STEP 2:
    # The Nexus construction has started.
    #
    # Send ALL workers to the new base.
    # ==========================================================

     if not self.relocation_workers_sent:

        for worker in self.workers:

            worker.move(self.relocation_location)

        self.relocation_workers_sent = True


    # ==========================================================
    # STEP 3:
    # Find the Nexus at the relocation location.
    #
    # We specifically look near the new location so we don't
    # accidentally select the original Nexus.
    # ==========================================================

     nexus = self.structures(U.NEXUS).closer_than(
        5,
        self.relocation_location
     )

     if not nexus.exists:
        return

     new_nexus = nexus.closest_to(
        self.relocation_location
     )


    # ==========================================================
    # STEP 4:
    # Nexus is still being constructed.
    #
    # DO NOTHING.
    #
    # All workers stay at the new base.
    # ==========================================================

     if not new_nexus.is_ready:
        return


    # ==========================================================
    # STEP 5:
    # Nexus is COMPLETE.
    #
    # Find the minerals closest to the new Nexus.
    # ==========================================================

     minerals = self.mineral_field.closest_to(
        new_nexus
     )

     if not minerals:
        return


    # ==========================================================
    # STEP 6:
    # Send ALL workers to mine.
    # ==========================================================

     for worker in self.workers:

        worker.gather(minerals)


    # ==========================================================
    # Relocation experiment is complete.
    # ==========================================================

     self.relocation_complete = True


    async def build_workers(self):

    # ==========================================================
    # Only start normal worker production after relocation.
    # ==========================================================

     if not self.relocation_complete:
        return


    # ==========================================================
    # We want 22 workers total.
    # ==========================================================

     if self.workers.amount >= 22:
        return


    # ==========================================================
    # Find our relocated Nexus.
    # ==========================================================

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


    # ==========================================================
    # Nexus must be completed before producing workers.
    # ==========================================================

     if not nexus.is_ready:
        return


    # ==========================================================
    # Build a Probe if we can afford one.
    # ==========================================================

     if (
        self.can_afford(U.PROBE)
        and self.supply_left > 0
        and not self.already_pending(U.PROBE)
     ):

        nexus.train(U.PROBE)


    

    
    
    async def manage_workers_and_gas(self):

    # ==========================================================
    # ONLY RUN AFTER RELOCATION IS COMPLETE
    # ==========================================================

     if not self.relocation_complete:
        return

     if self.relocation_location is None:
        return


    # ==========================================================
    # FIND THE NEW NEXUS
    # ==========================================================

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


    # ==========================================================
    # FIND GEYSERS AROUND THE NEW NEXUS
    # ==========================================================

     geysers = self.vespene_geyser.closer_than(
        10,
        nexus
     )

     if not geysers.exists:
        return


    # ==========================================================
    # FIND ASSIMILATORS ALREADY BUILT / BEING BUILT
    # ==========================================================

     assimilators = self.structures(U.ASSIMILATOR).closer_than(
        10,
        nexus
     )


    # ==========================================================
    # BUILD ASSIMILATORS
    #
    # Build ONE at a time.
    #
    # We deliberately return immediately after issuing the
    # build order so we don't try to use that same worker
    # again during this iteration.
    # ==========================================================

     for geyser in geysers:

        # Is there already an Assimilator on this geyser?
        if assimilators.closer_than(1.5, geyser).exists:
            continue

        # Don't start another one if we can't afford it.
        if not self.can_afford(U.ASSIMILATOR):
            break

        # Find an available worker.
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

        # IMPORTANT:
        # Stop here for this game step.
        return


    # ==========================================================
    # REFRESH ASSIMILATORS
    # ==========================================================

     assimilators = self.structures(U.ASSIMILATOR).closer_than(
        10,
        nexus
     )


    # ==========================================================
    # PUT 3 WORKERS ON EACH COMPLETED ASSIMILATOR
    #
    # Only use IDLE workers.
    #
    # Workers currently constructing something won't be
    # touched.
    # ==========================================================

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


    # ==========================================================
    # FIND MINERALS AROUND THE NEW NEXUS
    # ==========================================================

     minerals = self.mineral_field.closer_than(
        10,
        nexus
     )

     if not minerals.exists:
        return


    # ==========================================================
    # SEND ALL REMAINING IDLE WORKERS TO MINERALS
    # ==========================================================

     mineral_patch = minerals.closest_to(
        nexus
     )

     for worker in self.workers.idle:

        worker.gather(
            mineral_patch
        )

    async def build_workers(self):

    # ==========================================================
    # Only start normal worker production after relocation.
    # ==========================================================

     if not self.relocation_complete:
        return

    # ==========================================================
    # Stop once we have 22 workers.
    # ==========================================================

     if self.workers.amount >= self.worker_target:
        return

    # ==========================================================
    # Find our new Nexus.
    # ==========================================================

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

    # ==========================================================
    # Make sure the Nexus isn't already making a worker.
    # ==========================================================

     if nexus.is_idle and self.can_afford(U.PROBE):
        nexus.train(U.PROBE)

   
    async def build_gas(self):

    # ==========================================================
    # Only build gas after relocation is complete.
    # ==========================================================

     if not self.relocation_complete:
        return

     if self.relocation_location is None:
        return


    # ==========================================================
    # Find the NEW Nexus.
    # ==========================================================

     nexuses = self.structures(U.NEXUS).closer_than(
        5,
        self.relocation_location
     )

     if not nexuses.exists:
        return

     new_nexus = nexuses.closest_to(
        self.relocation_location
     )

     if not new_nexus.is_ready:
        return


    # ==========================================================
    # Find the geysers belonging to the NEW base.
    # ==========================================================

     geysers = self.vespene_geyser.closer_than(
        10,
        new_nexus
     )

     if not geysers.exists:
        return


    # ==========================================================
    # Find Assimilators already built at the NEW base.
    # ==========================================================

     assimilators = self.structures(U.ASSIMILATOR).closer_than(
        10,
        new_nexus
     )


    # ==========================================================
    # Build missing Assimilators.
    #
    # We deliberately DO NOT use:
    #
    # self.already_pending(U.ASSIMILATOR)
    #
    # because that is what caused the KeyError: 4135.
    # ==========================================================

     for geyser in geysers:

        # Already have an Assimilator on this geyser.
        if assimilators.closer_than(1, geyser).exists:
            continue


        # If we are already waiting for an Assimilator to
        # appear, don't issue another build command.
        if self.gas_build_started:
            return


        # Need 75 minerals for an Assimilator.
        if not self.can_afford(U.ASSIMILATOR):
            return


        # ======================================================
        # Find a worker at/near the new base.
        # ======================================================

        workers = self.workers.closer_than(
            10,
            new_nexus
        )

        if not workers.exists:
            return


        # Prefer an idle worker.
        idle_workers = workers.idle

        if idle_workers.exists:
            worker = idle_workers.random
        else:
            # If none are idle, use a worker closest to the
            # geyser.
            worker = workers.closest_to(geyser)


        # ======================================================
        # Build the Assimilator.
        # ======================================================

        await self.build(
            U.ASSIMILATOR,
            near=geyser,
            build_worker=worker
        )


        # Remember that we have just started construction.
        self.gas_build_started = True

        return


    # ==========================================================
    # If we reach this point, all available geysers have
    # Assimilators.
    #
    # Reset the flag so the function remains safe.
    # ==========================================================

     self.gas_build_started = False



    async def manage_workers(self):

    # ==========================================================
    # Only manage workers after relocation.
    # ==========================================================

     if not self.relocation_complete:
        return

     if self.relocation_location is None:
        return

    # ==========================================================
    # Find the new Nexus.
    # ==========================================================

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

    # ==========================================================
    # Find completed Assimilators at the new base.
    # ==========================================================

     assimilators = self.structures(U.ASSIMILATOR).closer_than(
        10,
        nexus
     ).ready

    # ==========================================================
    # Put workers onto gas.
    # ==========================================================

     for assimilator in assimilators:

        while (
            assimilator.assigned_harvesters < 3
            and self.workers.idle.exists
        ):

            worker = self.workers.idle.random

            worker.gather(assimilator)

    # ==========================================================
    # Find minerals around the new Nexus.
    # ==========================================================

     minerals = self.mineral_field.closer_than(
        10,
        nexus
     )

     if not minerals.exists:
        return

    # ==========================================================
    # Send remaining idle workers to minerals.
    # ==========================================================

     mineral = minerals.closest_to(nexus)

     for worker in self.workers.idle:
 
        worker.gather(mineral)

    # ---------- MAIN LOOP ----------

    
    async def on_step(self, iteration: int):

    # ==========================================================
    # FIRST: relocation experiment
    # ==========================================================

      await self.start_relocation()

    # ==========================================================
    # NORMAL DEVELOPMENT ONLY STARTS AFTER RELOCATION.
    # ==========================================================

      if not self.relocation_complete:
        return

    # ==========================================================
    # Keep producing workers until we reach 22.
    # ==========================================================

      await self.build_workers()

    # ==========================================================
    # Get both Assimilators built as quickly as possible.
    # ==========================================================

      await self.build_gas()

    # ==========================================================
    # Keep workers assigned to gas/minerals.
    # ==========================================================

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
