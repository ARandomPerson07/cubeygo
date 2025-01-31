import discord
import os
import random
from enum import Enum
from collections import defaultdict, OrderedDict
import discord.context_managers
from dotenv import load_dotenv
from discord.ext import commands
from typing import List, DefaultDict, OrderedDict
from hands import get_cards_from_hands, generate_ydk_from_hands

load_dotenv()
TOKEN = os.getenv('DISC_TOKEN')

intents = discord.Intents.default()
intents.message_content = True  # Enable if you plan to read message content
bot = commands.Bot(command_prefix='_', intents=intents)

class sessionStates(Enum):
    IDLE = 1
    RECRUITING = 2
    RECRUITEND = 3
    FIRSTROUND = 4
    FIRSTROUNDEND = 5
    SECONDROUND = 6
    SECONDROUNDEND = 7
    THIRDROUND = 8
    THIRDROUNDEND = 9


class Session:
    def __init__(self, channel : discord.TextChannel, recruitmsg : discord.Message = None):
        self.channel = channel
        self.recruitmsg = recruitmsg
        self.players : set[discord.User] = set()
        self.playerHands : DefaultDict[discord.User, List] = defaultdict(lambda: None)
        self.playerDraftHands : OrderedDict[discord.User, List] = OrderedDict()
        self.box = random.sample(range(75), 60)
        self.roundBox = []
        self.roundResponses = defaultdict(lambda : False)
        self.state = sessionStates.IDLE

    async def addPlayer(self, player: discord.user.User):
        global playerToSession
        playerToSession[player] = self
        if player not in self.players:
            self.players.add(player)
            await self.channel.send(f"Added {player.display_name}")
        else:
            await self.channel.send(f"{player.display_name}, you're already in!")
    async def initPlayers(self):
        assert self.state == sessionStates.RECRUITEND
        for player in self.players:
            self.playerHands[player] = []
        
    def getNextRound(self):
        if self.state == sessionStates.RECRUITEND:
            return sessionStates.FIRSTROUND
        elif self.state == sessionStates.FIRSTROUNDEND:
            return sessionStates.SECONDROUND
        elif self.state == sessionStates.SECONDROUNDEND:
            return sessionStates.THIRDROUND
        else:
            return None
        
    def endCurrentRound(self):
        #print("invoked end")
        success = False
        if self.state == sessionStates.FIRSTROUND:
            self.state = sessionStates.FIRSTROUNDEND
            success = True
        elif self.state == sessionStates.SECONDROUND:
            self.state = sessionStates.SECONDROUNDEND
            success = True
        elif self.state == sessionStates.THIRDROUND:
            self.state = sessionStates.THIRDROUNDEND
            success = True
        else:
            return success
    
    def rotateHands(self) -> bool:
        "Returns true if the hands were rotated, and false if the hands to be rotated were empty"
        ordPlayers = list(self.playerDraftHands.keys())
        ordDraftHands = list(self.playerDraftHands.values())
        if len(ordDraftHands[0]) <= 0:
            return False
        ordDraftHands.insert(0,ordDraftHands.pop())
        for i,player in enumerate(ordPlayers):
            self.playerDraftHands[player] = ordDraftHands[i]
        return True      
          
sessions = []
channelToSession : DefaultDict[discord.TextChannel, Session] = defaultdict(lambda : None)
playerToSession: DefaultDict[discord.User, Session] = defaultdict(lambda: None)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.listen('on_reaction_add')
async def process_recruitment(reaction : discord.Reaction, user : discord.User):
    if user == bot.user:
        return
    channel = reaction.message.channel
    if not channelToSession[channel]:
        return None
    else:
        session = channelToSession[channel]
        if reaction.message != session.recruitmsg:
            return
        if session.state == sessionStates.RECRUITING:
            await session.addPlayer(user)
        if len(session.players) >= 4:
            session.players = session.players[:4]
            if session.state != sessionStates.RECRUITEND:
                session.state = sessionStates.RECRUITEND
                await session.initPlayers()
                await channel.send("Recruitment automatically closed due to 4 players")

@bot.command()
@commands.dm_only()
async def choose(ctx : commands.Context, choice : str):
    user = ctx.author
    if user not in playerToSession.keys():
        ctx.send("Sorry, I couldn't find you in any active session.")
    else:
        session = playerToSession[user]
        hands = session.playerDraftHands[user]
        if session.roundResponses[user]:
            await ctx.send("Please await the other players before attempting to choose again")
        elif int(choice) not in hands:
            await ctx.send(f"Please choose a hand from {", ".join([str(x) for x in hands])}")
        else:
            session.playerHands[user].append(int(choice))
            hands.remove(int(choice))
            session.roundResponses[user] = True
            await ctx.send(f"Succesfully chose {choice}, please wait...")
            # handle end of pick
            if sum(session.roundResponses.values()) >= len(session.players):
                session.roundResponses = defaultdict(lambda : False)
                for player in session.players:
                    await player.dm_channel.send("Everyone has chosen, moving to next pick...")
                if not session.rotateHands():
                    # handle end of round
                    session.endCurrentRound()
                    for player in session.players:
                        await player.dm_channel.send(f"Round complete\nPlease check back with the server's channel.\nHere's what you have so far:", embed = get_cards_from_hands(session.playerHands[player], False))
                        if session.state == sessionStates.FIRSTROUNDEND:
                            #print(generate_ydk_from_hands(session.playerHands[player]))
                            await player.dm_channel.send(f"Here's a ydk with your choices:\n ```\n{generate_ydk_from_hands(session.playerHands[player])}```")

                    await session.channel.send("Round complete.")
                else:
                    for player in session.players:
                        await player.dm_channel.send(embed = get_cards_from_hands(session.playerDraftHands[player]))

@bot.command()
async def force(ctx):
    session = channelToSession[ctx.channel]
    if not session:
        await ctx.send("No session found for this channel.")
    elif session.state not in [sessionStates.FIRSTROUND, sessionStates.SECONDROUND, sessionStates.THIRDROUND]:
        await ctx.send("Session is not in a drafting round. Cannot force check.")
    elif sum(session.roundResponses.values()) >= len(session.players):
        session.roundResponses = defaultdict(lambda : False)
        for player in session.players:
            await player.dm_channel.send("Everyone has chosen, moving to next pick...")
        if not session.rotateHands():
            # handle end of round
            session.endCurrentRound()
            for player in session.players:
                await player.dm_channel.send(f"Round complete\nPlease check back with the server's channel.\nHere's what you have so far:", embed = get_cards_from_hands(session.playerHands[player]))
                if session.state == sessionStates.THIRDROUNDEND:
                    print(generate_ydk_from_hands(session.playerHands[player]))
                    await player.dm_channel.send(f"Here's a ydk with your choices:\n ```{generate_ydk_from_hands(session.playerHands[player])}```")
            await session.channel.send("Round complete.")
        else:
            for player in session.players:
                await player.dm_channel.send(f"Please choose a hand from: {", ".join([str(x) for x in session.playerDraftHands[player]])}")
    else:
        await ctx.send("Players are still choosing.")


@bot.command()
async def state(ctx, newstate :int = None):
    session = channelToSession[ctx.channel]
    if newstate:
        session.state = newstate
        await ctx.send(f"Changed state to {session.state}")
    else:
        await ctx.send(f"Current state: {session.state}")


@bot.command()
async def startcube(ctx):
    channel = ctx.channel
    session = channelToSession[channel]
    if session:
        await ctx.send("Cube in progress for this channel!")
    else:
        msg = await ctx.send("React to this message to join!")
        newSession = Session(channel, msg)
        newSession.state = sessionStates.RECRUITING
        channelToSession[channel] = newSession
    
@bot.command()
async def closerec(ctx):
    session = channelToSession[ctx.channel]
    if session.state != sessionStates.RECRUITING:
        await ctx.send("Attempted to close session not already recruiting")
        return
    else:
        session.state = sessionStates.RECRUITEND
        players = session.players
        playersString = " ".join([user.display_name for user in players])
        await session.initPlayers()
        await ctx.send(f"Session closed! Players are {playersString}")

@bot.command()
async def startround(ctx):
    session = channelToSession[ctx.channel]
    if not session:
        await ctx.send("Session not found! Did you create one with `startcube`?")
        return
    elif session.getNextRound() is None:
        await ctx.send("Session is not in a valid state to start new round.")
        return
    else:
        roundSize = len(session.players) * 5
        assert len(session.box) >= roundSize
        random.shuffle(session.box)
        session.roundBox = session.box[:roundSize]
        session.box = session.box[roundSize:]
        session.state = session.getNextRound()
        for player in session.players:
            session.playerDraftHands[player] = session.roundBox[:5]
            session.roundBox = session.roundBox[5:]
            if player.dm_channel is None:
                dm_channel = await player.create_dm()
            else:
                dm_channel = player.dm_channel
            session.roundResponses[player] = False
            #await dm_channel.send(f"Please choose from the following hands: {", ".join([str(x) for x in session.playerDraftHands[player]])}")
            await dm_channel.send(embed = get_cards_from_hands(session.playerDraftHands[player]))

@bot.command()
async def closedraft(ctx):
    session = channelToSession[ctx.channel]
    if not session:
        await ctx.send("No session to close!")
    else:
        channelToSession[ctx.channel].state = sessionStates.IDLE
        channelToSession[ctx.channel] = None
        for player in session.players:
            playerToSession.pop(player,None)
        await ctx.send("Session has been closed!")


@bot.command()
async def hello(ctx):
    await ctx.send('Hello! I am your bot.')

bot.run(TOKEN)