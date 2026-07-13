from sc2.main import run_game
from sc2.maps import get as get_map
from sc2.data import Race, Difficulty
from sc2.player import Bot, Computer
from sc2.bot_ai import BotAI
from sc2.ids.unit_typeid import UnitTypeId as U
from sc2.ids.ability_id import AbilityId as A

class SimpleZergBot(BotAI):
    async def on_start(self):
        self.attack_started = False
        

    async def on_step(self, iteration: int):
        await self.distribute_workers()
        await self.build_overlords()
        await self.expand()
        await self.take_gas()
        await self.drone_up()
        await self.tech_pool()
        await self.queens_and_injects()
        await self.produce_army()
        await self.attack()

    # ---------- helpers ----------
    async def build_overlords(self):
        if (
            self.supply_left < 3
            and self.already_pending(U.OVERLORD) == 0
            and self.can_afford(U.OVERLORD)
        ):
            self.train(U.OVERLORD)

    async def expand(self):
        if (
            self.townhalls.ready.amount < 6
            and self.can_afford(U.HATCHERY)
            and self.already_pending(U.HATCHERY) == 0
            and self.supply_used >= 18
        ):
            await self.expand_now()

    async def take_gas(self):
        if self.structures(U.EXTRACTOR).amount < 1 and self.can_afford(U.EXTRACTOR) and self.townhalls.ready:
            geyser = self.vespene_geyser.closer_than(10, self.townhalls.ready.first).first
            await self.build(U.EXTRACTOR, geyser)

    async def drone_up(self):
        ideal = sum(h.ideal_harvesters for h in self.townhalls.ready)
        if self.workers.amount < min(ideal, 44) and self.supply_left > 0 and self.can_afford(U.DRONE):
            self.train(U.DRONE)

    async def tech_pool(self):
        if self.structures(U.SPAWNINGPOOL).amount == 0 and self.can_afford(U.SPAWNINGPOOL) and self.townhalls.ready:
            pos = self.townhalls.ready.first.position.towards(self.game_info.map_center, 5)
            await self.build(U.SPAWNINGPOOL, near=pos)

    async def queens_and_injects(self):
        # Queens: one per hatch
        if self.structures(U.SPAWNINGPOOL).ready and self.townhalls.ready:
            if self.units(U.QUEEN).amount < self.townhalls.ready.amount and self.can_afford(U.QUEEN):
                self.train(U.QUEEN)

        # Injects
        for q in self.units(U.QUEEN).ready.idle:
            if q.energy >= 25 and self.townhalls.ready:
                abilities = await self.get_available_abilities(q)
                if A.EFFECT_INJECTLARVA in abilities:
                    q(A.EFFECT_INJECTLARVA, self.townhalls.ready.closest_to(q))

    async def produce_army(self):
        # Lings after pool
        if self.structures(U.SPAWNINGPOOL).ready and self.can_afford(U.ZERGLING) and self.supply_left >= 2:
            self.train(U.ZERGLING)

    async def attack(self):
        lings = self.units(U.ZERGLING).ready
        if not self.attack_started and lings.amount >= 20:
            self.attack_started = True
            target = self.enemy_start_locations[0]
            for u in lings:
                u.attack(target)

        if self.attack_started:
            for u in lings.idle:
                u.attack(self.enemy_start_locations[0])

if __name__ == "__main__":
    run_game(
        get_map("AbyssalReefLE"),
        [Bot(Race.Zerg, SimpleZergBot()), Computer(Race.Terran, Difficulty.Easy)],
        realtime=True,
    )
