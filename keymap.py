"""Раскладка клавиш: какой звук на какой кнопке.

Каждый банк = сетка 6 строк x 14 столбцов. Пути указаны относительно папки sounds/.
None = пустая клавиша. Ячейки [0][0] и [5][0..2] заняты служебными функциями,
всё, что туда записано, игнорируется.

Можно свободно переставлять, менять и добавлять банки (кнопка [0][0] листает их по кругу).
"""

BANKS = [
    {
        "name": "Combat",  # fight + creatures + people
        "keys": [
            # строка 0
            [
                None,                                      # [0][0]
                "fight/armor_hit_heavy.ogg",               # [0][1]
                "fight/armor_hit_light.ogg",               # [0][2]
                "fight/arrow_flyby.ogg",                   # [0][3]
                "fight/arrow_hit_metal.ogg",               # [0][4]
                "fight/arrow_hit_stone.ogg",               # [0][5]
                "fight/arrow_hit_wood.ogg",                # [0][6]
                "fight/axe_hit.ogg",                       # [0][7]
                "fight/blade_whoosh.ogg",                  # [0][8]
                "fight/bow_shot_01.ogg",                   # [0][9]
                "fight/bow_shot_02.ogg",                   # [0][10]
                "fight/club_hit.ogg",                      # [0][11]
                "fight/crossbow_shot.ogg",                 # [0][12]
                "fight/dagger_stab_01.ogg",                # [0][13]
            ],
            # строка 1
            [
                "fight/dagger_stab_02.ogg",                # [1][0]
                "fight/flail_hit.ogg",                     # [1][1]
                "fight/flesh_hit.ogg",                     # [1][2]
                "fight/flesh_stab.ogg",                    # [1][3]
                "fight/hatchet_throw.ogg",                 # [1][4]
                "fight/mace_hit.ogg",                      # [1][5]
                "fight/miss_whoosh_01.ogg",                # [1][6]
                "fight/miss_whoosh_02.ogg",                # [1][7]
                "fight/punch_heavy.ogg",                   # [1][8]
                "fight/shield_block_metal.ogg",            # [1][9]
                "fight/shield_block_wood.ogg",             # [1][10]
                "fight/sling_shot.ogg",                    # [1][11]
                "fight/spear_thrust.ogg",                  # [1][12]
                "fight/sword_clash_01.ogg",                # [1][13]
            ],
            # строка 2
            [
                "fight/sword_clash_02.ogg",                # [2][0]
                "fight/sword_clash_03.ogg",                # [2][1]
                "fight/sword_clash_04.ogg",                # [2][2]
                "fight/sword_draw_01.ogg",                 # [2][3]
                "fight/sword_draw_02.ogg",                 # [2][4]
                "fight/sword_hit.ogg",                     # [2][5]
                "fight/sword_swing_01.ogg",                # [2][6]
                "fight/throwing_knife.ogg",                # [2][7]
                "fight/warhammer_hit.ogg",                 # [2][8]
                "creatures/bat_screech.ogg",               # [2][9]
                "creatures/bat_wings.ogg",                 # [2][10]
                "creatures/claw_slash.ogg",                # [2][11]
                "creatures/dragon_screech.ogg",            # [2][12]
                "creatures/drake_roar.ogg",                # [2][13]
            ],
            # строка 3
            [
                "creatures/ghost_wail.ogg",                # [3][0]
                "creatures/ghoul_hiss.ogg",                # [3][1]
                "creatures/giant_snake_hiss.ogg",          # [3][2]
                "creatures/goblin_shriek.ogg",             # [3][3]
                "creatures/lich_death_wail.ogg",           # [3][4]
                "creatures/monster_bite.ogg",              # [3][5]
                "creatures/monster_roar_01.ogg",           # [3][6]
                "creatures/monster_roar_02.ogg",           # [3][7]
                "creatures/ogre_grunt.ogg",                # [3][8]
                "creatures/orc_death.ogg",                 # [3][9]
                "creatures/orc_grunt.ogg",                 # [3][10]
                "creatures/pincer_snap.ogg",               # [3][11]
                "creatures/skeleton_collapse.ogg",         # [3][12]
                "creatures/skeleton_rattle.ogg",           # [3][13]
            ],
            # строка 4
            [
                "creatures/slime_squish.ogg",              # [4][0]
                "creatures/snake_hiss.ogg",                # [4][1]
                "creatures/tail_whip.ogg",                 # [4][2]
                "creatures/treant_slam.ogg",               # [4][3]
                "creatures/troll_death.ogg",               # [4][4]
                "creatures/troll_roar.ogg",                # [4][5]
                "creatures/wolf_death.ogg",                # [4][6]
                "creatures/wolf_growl.ogg",                # [4][7]
                "creatures/wolf_yelp.ogg",                 # [4][8]
                "creatures/yeti_roar.ogg",                 # [4][9]
                "creatures/zombie_groan.ogg",              # [4][10]
                "people/battle_cry_01.ogg",                # [4][11]
                "people/battle_cry_02.ogg",                # [4][12]
                "people/dwarf_pain.ogg",                   # [4][13]
            ],
            # строка 5
            [
                None,                                      # [5][0]
                None,                                      # [5][1]
                None,                                      # [5][2]
                "people/female_death.ogg",                 # [5][3]
                "people/female_pain.ogg",                  # [5][4]
                "people/gasp_inhale.ogg",                  # [5][5]
                "people/groan.ogg",                        # [5][6]
                "people/male_death.ogg",                   # [5][7]
                "people/male_pain.ogg",                    # [5][8]
                "people/old_man_pain.ogg",                 # [5][9]
                "people/scream.ogg",                       # [5][10]
                "people/sigh_exhale.ogg",                  # [5][11]
                None,                                      # [5][12]
                None,                                      # [5][13]
            ],
        ],
    },
    {
        "name": "Magic",  # magic + nature + animals + table
        "keys": [
            # строка 0
            [
                None,                                      # [0][0]
                "magic/arcane_bolt.ogg",                   # [0][1]
                "magic/black_tentacles.ogg",               # [0][2]
                "magic/blizzard.ogg",                      # [0][3]
                "magic/counterspell.ogg",                  # [0][4]
                "magic/earthquake.ogg",                    # [0][5]
                "magic/entangle.ogg",                      # [0][6]
                "magic/faerie_fire.ogg",                   # [0][7]
                "magic/fire_bolt.ogg",                     # [0][8]
                "magic/fire_breath.ogg",                   # [0][9]
                "magic/flame_strike.ogg",                  # [0][10]
                "magic/greater_restoration.ogg",           # [0][11]
                "magic/healing.ogg",                       # [0][12]
                "magic/holy_smite.ogg",                    # [0][13]
            ],
            # строка 1
            [
                "magic/illusion.ogg",                      # [1][0]
                "magic/levitate.ogg",                      # [1][1]
                "magic/lightning_bolt.ogg",                # [1][2]
                "magic/magic_missile.ogg",                 # [1][3]
                "magic/magic_shield.ogg",                  # [1][4]
                "magic/necrotic_blast.ogg",                # [1][5]
                "magic/petrify.ogg",                       # [1][6]
                "magic/poison_acid.ogg",                   # [1][7]
                "magic/polymorph.ogg",                     # [1][8]
                "magic/potion_drink.ogg",                  # [1][9]
                "magic/shadow_bolt.ogg",                   # [1][10]
                "magic/slow.ogg",                          # [1][11]
                "magic/summon_creature.ogg",               # [1][12]
                "magic/time_stop.ogg",                     # [1][13]
            ],
            # строка 2
            [
                "magic/water_blast.ogg",                   # [2][0]
                "nature/birds_chirp.ogg",                  # [2][1]
                "nature/explosion_01.ogg",                 # [2][2]
                "nature/explosion_02.ogg",                 # [2][3]
                "nature/fire_crackle.ogg",                 # [2][4]
                "nature/fire_extinguish.ogg",              # [2][5]
                "nature/fire_ignite.ogg",                  # [2][6]
                "nature/flint_and_steel.ogg",              # [2][7]
                "nature/ice_crack.ogg",                    # [2][8]
                "nature/lava_bubble.ogg",                  # [2][9]
                "nature/leaves_rustle.ogg",                # [2][10]
                "nature/rockslide.ogg",                    # [2][11]
                "nature/thunder_01.ogg",                   # [2][12]
                "nature/thunder_02.ogg",                   # [2][13]
            ],
            # строка 3
            [
                "nature/thunder_rolling.ogg",              # [3][0]
                "nature/torch_whoosh.ogg",                 # [3][1]
                "nature/tree_falling.ogg",                 # [3][2]
                "nature/water_bubble.ogg",                 # [3][3]
                "nature/water_splash.ogg",                 # [3][4]
                "nature/wind_gust_leaves.ogg",             # [3][5]
                "nature/wind_gust.ogg",                    # [3][6]
                "animals/cart_rolling.ogg",                # [3][7]
                "animals/chicken.ogg",                     # [3][8]
                "animals/dog_bark.ogg",                    # [3][9]
                "animals/elephant_trumpet.ogg",            # [3][10]
                "animals/horse_death.ogg",                 # [3][11]
                "animals/horse_gallop.ogg",                # [3][12]
                "animals/horse_neigh.ogg",                 # [3][13]
            ],
            # строка 4
            [
                "animals/horse_snort.ogg",                 # [4][0]
                "animals/pig_squeal.ogg",                  # [4][1]
                "animals/sheep.ogg",                       # [4][2]
                "animals/ship_creak.ogg",                  # [4][3]
                "animals/ship_wreck.ogg",                  # [4][4]
                "table/alarm_horn.ogg",                    # [4][5]
                "table/defeat.ogg",                        # [4][6]
                "table/dice_roll_01.ogg",                  # [4][7]
                "table/dice_roll_02.ogg",                  # [4][8]
                "table/fanfare.ogg",                       # [4][9]
                "table/hero_arrives.ogg",                  # [4][10]
                "table/quest_objective.ogg",               # [4][11]
                "table/victory.ogg",                       # [4][12]
                "table/war_horn_01.ogg",                   # [4][13]
            ],
            # строка 5
            [
                None,                                      # [5][0]
                None,                                      # [5][1]
                None,                                      # [5][2]
                "table/war_horn_02.ogg",                   # [5][3]
                None,                                      # [5][4]
                None,                                      # [5][5]
                None,                                      # [5][6]
                None,                                      # [5][7]
                None,                                      # [5][8]
                None,                                      # [5][9]
                None,                                      # [5][10]
                None,                                      # [5][11]
                None,                                      # [5][12]
                None,                                      # [5][13]
            ],
        ],
    },
    {
        "name": "Explore",  # investigation + tavern
        "keys": [
            # строка 0
            [
                None,                                      # [0][0]
                "investigation/book_close.ogg",            # [0][1]
                "investigation/book_open.ogg",             # [0][2]
                "investigation/chest_close.ogg",           # [0][3]
                "investigation/chest_open.ogg",            # [0][4]
                "investigation/cloth_rustle.ogg",          # [0][5]
                "investigation/door_close.ogg",            # [0][6]
                "investigation/door_creak_01.ogg",         # [0][7]
                "investigation/door_creak_02.ogg",         # [0][8]
                "investigation/door_open.ogg",             # [0][9]
                "investigation/door_slam.ogg",             # [0][10]
                "investigation/floorboard_creak.ogg",      # [0][11]
                "investigation/footsteps_stone.ogg",       # [0][12]
                "investigation/footsteps_wood.ogg",        # [0][13]
            ],
            # строка 1
            [
                "investigation/fuse_burning.ogg",          # [1][0]
                "investigation/heartbeat.ogg",             # [1][1]
                "investigation/heavy_door_open.ogg",       # [1][2]
                "investigation/iron_bars_open.ogg",        # [1][3]
                "investigation/lock_latch.ogg",            # [1][4]
                "investigation/lockpick_click.ogg",        # [1][5]
                "investigation/page_flip.ogg",             # [1][6]
                "investigation/pickaxe_hit.ogg",           # [1][7]
                "investigation/portcullis_fall.ogg",       # [1][8]
                "investigation/rumble.ogg",                # [1][9]
                "investigation/rummage_bag.ogg",           # [1][10]
                "investigation/secret_stone_door_close.ogg", # [1][11]
                "investigation/secret_stone_door_open.ogg", # [1][12]
                "investigation/trap_cave_in.ogg",          # [1][13]
            ],
            # строка 2
            [
                "investigation/trap_dart.ogg",             # [2][0]
                "investigation/unlock.ogg",                # [2][1]
                "investigation/water_drip.ogg",            # [2][2]
                "tavern/bag_drop.ogg",                     # [2][3]
                "tavern/blacksmith_anvil.ogg",             # [2][4]
                "tavern/chair_knock.ogg",                  # [2][5]
                "tavern/chopping_wood.ogg",                # [2][6]
                "tavern/coin_pouch.ogg",                   # [2][7]
                "tavern/coins_drop.ogg",                   # [2][8]
                "tavern/drink_gulp.ogg",                   # [2][9]
                "tavern/dwarf_laugh.ogg",                  # [2][10]
                "tavern/evil_laugh.ogg",                   # [2][11]
                "tavern/finger_snap.ogg",                  # [2][12]
                "tavern/glass_shatter_01.ogg",             # [2][13]
            ],
            # строка 3
            [
                "tavern/glass_shatter_02.ogg",             # [3][0]
                "tavern/hammering.ogg",                    # [3][1]
                "tavern/knuckle_crack.ogg",                # [3][2]
                "tavern/market_bustle.ogg",                # [3][3]
                "tavern/mugs_clink.ogg",                   # [3][4]
                "tavern/pot_clang.ogg",                    # [3][5]
                "tavern/sawing_wood.ogg",                  # [3][6]
                "tavern/table_slam.ogg",                   # [3][7]
                "tavern/temple_bell.ogg",                  # [3][8]
                "tavern/town_bell.ogg",                    # [3][9]
                "tavern/witch_cackle.ogg",                 # [3][10]
                None,                                      # [3][11]
                None,                                      # [3][12]
                None,                                      # [3][13]
            ],
            # строка 4
            [
                None,                                      # [4][0]
                None,                                      # [4][1]
                None,                                      # [4][2]
                None,                                      # [4][3]
                None,                                      # [4][4]
                None,                                      # [4][5]
                None,                                      # [4][6]
                None,                                      # [4][7]
                None,                                      # [4][8]
                None,                                      # [4][9]
                None,                                      # [4][10]
                None,                                      # [4][11]
                None,                                      # [4][12]
                None,                                      # [4][13]
            ],
            # строка 5
            [
                None,                                      # [5][0]
                None,                                      # [5][1]
                None,                                      # [5][2]
                None,                                      # [5][3]
                None,                                      # [5][4]
                None,                                      # [5][5]
                None,                                      # [5][6]
                None,                                      # [5][7]
                None,                                      # [5][8]
                None,                                      # [5][9]
                None,                                      # [5][10]
                None,                                      # [5][11]
                None,                                      # [5][12]
                None,                                      # [5][13]
            ],
        ],
    },
]

# Фоновые треки: листаются кнопками [5][0] (назад) и [5][1] (вперёд), играют по кругу.
BG_TRACKS = [
    "music/01_beginning_into_the_shadows.ogg",
    "music/02_fight_weight_of_revenge.ogg",
    "music/03_ending_revelation.ogg",
    "ambient/tavern.ogg",
    "ambient/town_market.ogg",
    "ambient/forest_day.ogg",
    "ambient/forest_night_camp.ogg",
    "ambient/dungeon.ogg",
    "ambient/cave.ogg",
    "ambient/harbor.ogg",
    "ambient/thunderstorm.ogg",
    "ambient/blizzard_mountains.ogg",
    "ambient/battlefield_distant.ogg",
]
