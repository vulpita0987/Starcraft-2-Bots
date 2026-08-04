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

    # Main base: Pylon near the top of the ramp
    # so it can power the cannon choke.
      if nexus.tag == self.townhalls.first.tag:

        return self.main_base_ramp.top_center.towards(
            self.start_location,
            5
        )

    # Expansions: Pylon near the Nexus
      return nexus.position.towards(
        self.game_info.map_center,
        5
      )


    
    async def manage_buildings(self):

    # ==========================================================
    # STAGE 1
    # Build ONE Forge first.
    # Nothing else is built until the Forge exists.
    # ==========================================================

     forge = self.structures(U.FORGE)

     if not forge.exists:

        if (
            self.can_afford(U.FORGE)
            and self.already_pending(U.FORGE) == 0
        ):

            nexus = self.townhalls.ready.first

            await self.build(
                U.FORGE,
                near=nexus.position.towards(
                    self.game_info.map_center,
                    6
                )
            )

        return


    # ==========================================================
    # STAGE 2
    # Main-base choke cannon wall
    #
    # Build exactly 5 Photon Cannons around the main ramp.
    # No other tech buildings are started until all 5
    # cannons are COMPLETE.
    # ==========================================================

     main_choke = self.main_base_ramp.top_center

     completed_cannons = self.structures(
        U.PHOTONCANNON
     ).ready.amount

     pending_cannons = self.already_pending(
        U.PHOTONCANNON
     )

     total_cannons = completed_cannons + pending_cannons

     if total_cannons < 5:

        if self.can_afford(U.PHOTONCANNON):

            # Spread the cannons along the choke.
            cannon_position = main_choke.towards(
                self.start_location,
                2 + total_cannons * 2
            )

            await self.build(
                U.PHOTONCANNON,
                near=cannon_position,
                placement_step=1
            )

        return


    # ==========================================================
    # STAGE 3
    # Five cannons are now COMPLETE.
    #
    # From this point onward we can construct the Carrier tech.
    # ==========================================================


    # ----------------------------------------------------------
    # Build Assimilators at ALL bases
    # ----------------------------------------------------------

     for nexus in self.townhalls.ready:

        nearby_assimilators = self.structures(
            U.ASSIMILATOR
        ).closer_than(12, nexus)

        if nearby_assimilators.amount < 2:

            gas_geysers = self.vespene_geyser.closer_than(
                12,
                nexus
            )

            for geyser in gas_geysers:

                if self.structures(U.ASSIMILATOR).closer_than(
                    2,
                    geyser
                ).exists:
                    continue

                if self.can_afford(U.ASSIMILATOR):

                    worker = self.workers.closest_to(geyser)

                    await self.build(
                        U.ASSIMILATOR,
                        near=geyser,
                        build_worker=worker
                    )

                    return


    # ----------------------------------------------------------
    # Build Gateway at ALL bases
    #
    # Gateways aren't strictly required for Carriers, but they
    # give you a proper Protoss production foundation.
    # ----------------------------------------------------------

     for nexus in self.townhalls.ready:

        nearby_gateways = self.structures(
            U.GATEWAY
        ).closer_than(15, nexus)

        if nearby_gateways.amount < 1:

            if self.can_afford(U.GATEWAY):

                await self.build(
                    U.GATEWAY,
                    near=nexus.position.towards(
                        self.game_info.map_center,
                        6
                    )
                )

                return


    # ==========================================================
    # STAGE 4
    # Stargates
    #
    # We want Stargates distributed across our bases.
    # One Stargate per base initially.
    # ==========================================================

     for nexus in self.townhalls.ready:

        nearby_stargates = self.structures(
            U.STARGATE
        ).closer_than(15, nexus)

        if nearby_stargates.amount < 1:

            if self.can_afford(U.STARGATE):

                await self.build(
                    U.STARGATE,
                    near=nexus.position.towards(
                        self.game_info.map_center,
                        7
                    )
                )

                return


    # ==========================================================
    # STAGE 5
    # Fleet Beacon
    #
    # Only ONE Fleet Beacon is required for the whole player.
    # It unlocks Carrier production.
    # ==========================================================

     if not self.structures(U.FLEETBEACON).exists:

        if self.can_afford(U.FLEETBEACON):

            # Put the Fleet Beacon near the first Nexus.
            nexus = self.townhalls.ready.first

            await self.build(
                U.FLEETBEACON,
                near=nexus.position.towards(
                    self.game_info.map_center,
                    8
                )
            )

            return


    def get_cannon_positions(self, nexus, cannon_number):
   

    # ==========================================================
    # MAIN BASE
    # ==========================================================

     if nexus.tag == self.townhalls.first.tag:

        choke = self.main_base_ramp.top_center

        # Move from the choke toward the main base.
        inside = choke.towards(
            self.start_location,
            3
        )

        # Five positions distributed around the choke.
        positions = [

            inside.towards(
                self.game_info.map_center,
                3
            ),

            inside.towards(
                self.game_info.map_center,
                3
            ).towards(
                self.main_base_ramp.bottom_center,
                2
            ),

            inside.towards(
                self.start_location,
                1
            ),

            inside.towards(
                self.main_base_ramp.bottom_center,
                2
            ),

            inside.towards(
                self.main_base_ramp.top_center,
                2
            )
        ]

        return positions[cannon_number]


    # ==========================================================
    # EXPANSIONS
    # ==========================================================

    # Defensive point between the Nexus and map centre.
     choke = nexus.position.towards(
        self.game_info.map_center,
        7
     )

    # Move slightly toward the Nexus so the cannons sit
    # behind/around the entrance rather than blocking it.
     inside = choke.towards(
        nexus.position,
        3
     )

     positions = [

        inside.towards(
            self.game_info.map_center,
            3
        ),

        inside.towards(
            self.game_info.map_center,
            3
        ).towards(
            nexus.position,
            2
        ),

        inside.towards(
            nexus.position,
            1
        ),

        inside.towards(
            nexus.position,
            2
        ).towards(
            self.game_info.map_center,
            2
        ),

        inside.towards(
            self.game_info.map_center,
            2
        )
     ]

     return positions[cannon_number]


  
    async def build_choke_cannons(self):

    # ==========================================================
    # 1. Do not build cannons until the Forge is COMPLETE
    # ==========================================================

     if not self.structures(U.FORGE).ready.exists:
        return


    # ==========================================================
    # 2. Go through every ready Nexus
    # ==========================================================

     for nexus in self.townhalls.ready:

        # Get the 5 positions you created in
        # get_cannon_positions()
        positions = self.get_cannon_positions(nexus)


        # ======================================================
        # 3. Check each of the five cannon positions
        # ======================================================

        for position in positions:

            # Find a completed cannon close to this position.
            # If one exists, this position is already defended.
            existing = self.structures(
                U.PHOTONCANNON
            ).closer_than(
                2,
                position
            )

            if existing.exists:
                continue


            # ==================================================
            # 4. Check if a cannon is already being constructed
            # near this position.
            # ==================================================

            pending = self.structures(
                U.PHOTONCANNON
            ).closer_than(
                2,
                position
            ).filter(
                lambda cannon: not cannon.is_ready
            )

            if pending.exists:
                continue


            # ==================================================
            # 5. Don't try to build if we can't afford it
            # ==================================================

            if not self.can_afford(U.PHOTONCANNON):
                return


            # ==================================================
            # 6. Find a worker
            # ==================================================

            worker = self.workers.closest_to(position)

            if worker is None:
                return


            # ==================================================
            # 7. Build the cannon
            #
            # placement_step=1 lets SC2 find a nearby valid
            # location if our desired position isn't exactly
            # buildable.
            # ==================================================

            await self.build(
                U.PHOTONCANNON,
                near=position,
                build_worker=worker,
                placement_step=1
            )

            # Only issue ONE cannon order per game step.
            return


    # ---------- MAIN LOOP ----------

    async def on_step(self, iteration: int):

        await self.manage_workers()
        await self.build_pylons()
        await self.build_choke_cannons()
        await self.manage_buildings()
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
