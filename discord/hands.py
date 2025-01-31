import pandas as pd
import discord
from typing import List

handdb = pd.read_csv("../hands.csv")

def get_cards_from_hands(hands: List[int], choosing = True) -> discord.Embed:
    if not choosing:
        title = "Your Trunk"
        description = ""
    else:
        title = "Hands"
        description = "Please choose from the following hands. Use `_choose <hand number>` (without the #) to make your selection."
    embed = discord.Embed(title= title,
                        description=description,
                        colour=0x00b0f4)

    for hand in hands:
        embed.add_field(name = "#" + str(hand),
                        value = "- " + "\n- ".join(list(handdb[handdb['hand']== hand].sort_values('base')['name'])),
                        inline = False)
    return embed

def generate_ydk_from_hands(hands:List[int]) -> str:
    rows = handdb[handdb['hand'].isin(hands)]
    main = "#main\n"
    extra = "#extra\n"
    ctr = 0
    ids = rows['id']
    for cid in ids:
        ctr += 1
        if ctr % 4 == 0:
            extra += f"{cid}\n"
        else:
            main += f"{cid}\n"
    outstr = main + "\n" + extra
    return outstr