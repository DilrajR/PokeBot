import discord
import os
import asyncio
import random
import json
import requests
from bs4 import BeautifulSoup

my_secret = os.environ['TOKEN']
# Connection to discord
client = discord.Client()

channelID = int(os.environ['channelID'])

# List of Pokémon that can spawn
pokemonList = []

# Overall Pokedex
completePokedex = {}

# Weights of the rarity of each pokemon
# Legendary = 1
# Ultra-rare = 3
# Rare = 10
# Uncommon = 25
# Common = 50
weights = []

# Dictionary to keep track of each users pokedex (which pokemon they have caught)
pokedex = {}

# Read through the file to extract each pokemon,
# along with their index number and rarity

with open('pokemonList.txt') as f:
    for line in f:
        pokemon = line.strip().split(',')
        pokemonList.append([pokemon[0], pokemon[1]])
        completePokedex[pokemon[1]] = pokemon[0]
        if pokemon[2].lower() == 'legendary':
            weights.append(1)
        elif pokemon[2].lower() == 'ultra-rare':
            weights.append(3)
        elif pokemon[2].lower() == 'rare':
            weights.append(10)
        elif pokemon[2].lower() == 'uncommon':
            weights.append(25)
        elif pokemon[2].lower() == 'common':
            weights.append(50)
        else:
            weights.append(0)

# Global variables to manage the Pokémon spawning and cooldown
spawnedPokemon = None
catch = False
spawnEvent = asyncio.Event()


@client.event
async def on_ready():
    print(f'We have logged in as {client.user.name} ({client.user.id})')
    loadPokedex()
    channel = client.get_channel(channelID)
    await channel.send(
        "Welcome to the Pokemon world! To begin your journey, type '$start'\nIf you have already began your journey, goodluck on catching 'em all! You may type '$help' if you forget any command'"
    )

    client.loop.create_task(sendRecurringMessage(
        client.get_channel(channelID)))


@client.event
async def on_message(message):
    global spawnedPokemon, catch, spawnEvent, completePokedex
    print("Message Received")
    if message.author == client.user:
        return

    channel = client.get_channel(channelID)

    if message.content.startswith('$hello'):
        await channel.send('Hello!')

    if message.content.lower() == '$start':
        if str(message.author.id) not in pokedex:
            pokedex[message.author.id] = {}
            for pokemonEntry in pokemonList:
                pokedex[message.author.id][pokemonEntry[0]] = '???'
            await channel.send(
                "You now have acquired a Pokedex. This keeps track of all the new Pokemon you have caught. To open your pokedex, type '$pokedex'. You must fill up your Pokedex by catching new Pokemon. In order to catch a Pokemon, type '$catch'. A Pokemon is only able to be caught by one trainer, so be on the lookout!"
            )
            savePokedex()
            loadPokedex()
        else:
            await resetPokedex(message)

    if message.content.lower() == '$pokedex':
        if pokedex.get(str(message.author.id)):
            userPokedex = pokedex.get(str(message.author.id))
            pokedexMessage = "  ".join([
                f"{pokemonNum}. {pokemon}"
                for pokemonNum, pokemon in userPokedex.items()
            ])
            await channel.send(pokedexMessage)
            await channel.send("To learn more about the Pokemon, type '$description' along with its Pokedex number. For example: $description 001")
        else:
            await channel.send(
                "You do not have a Pokedex yet! Please type '$start' in order to begin your adventure!"
            )
        
    if message.content.startswith('$description'):
       userPokedex = pokedex.get(str(message.author.id))
       _, pokedexNum = message.content.split(' ', 1)
       pokedexNum = pokedexNum.strip()
       print(pokedexNum)
       if pokedexNum in userPokedex:
         if userPokedex[pokedexNum] != "???":
            await channel.send(getPokemonDescription(userPokedex[pokedexNum]))
         else:
            await channel.send(f'No information on #{pokedexNum} within your Pokedex. You must first capture it to fill out the information')
       else:
         await channel.send('Invalid Pokedex Number!')

    if message.content.lower() == '$catch':
        if spawnedPokemon is None:
            await channel.send('No Pokémon to catch right now!')
        elif catch:
            await channel.send(
                f"{spawnedPokemon} was already caught. Wait for the next spawn!"
            )
        else:
            catch = True
            userPokedex = pokedex.get(str(message.author.id))
            if spawnedPokemon == userPokedex[completePokedex[spawnedPokemon]]:
                await channel.send(f"You caught a {spawnedPokemon}!")
                await channel.send(
                    f'{spawnedPokemon} has already been registered to your Pokedex'
                )
                userPokedex[completePokedex[spawnedPokemon]] = spawnedPokemon
            if spawnedPokemon != userPokedex[completePokedex[spawnedPokemon]]:
                userPokedex[completePokedex[spawnedPokemon]] = spawnedPokemon
                await channel.send(f"You caught a {spawnedPokemon}!")
                await channel.send('You have registered a new Pokemon!')
            savePokedex()
            loadPokedex()
          
    if message.content.lower() == '$help':
       channel.send("$start - Begin your journey or if you have already began your journey, reset your Pokedex\n$catch - Catch wild Pokemon that have appeared to register them to your Pokedex\n$pokedex - Bring up your Pokedex to see which Pokemon you have caught and which Pokemon are still unknown\n$description - Your Pokedex reads you the description of the Pokemon you have registered. Use this command like such: $description 001\nGoodluck on your adventure!")


async def sendRecurringMessage(channel):
    global spawnedPokemon, catch, spawnEvent
    await client.wait_until_ready()

    while not client.is_closed():
        if not spawnedPokemon:
            # Spawn a new Pokémon along with it's sprite
            spawnedPokemon = getNextPokemon()
            iconNumber = int(str(completePokedex[spawnedPokemon]))
            pokemonIconLocation = os.path.join("gen 1 Icons", f"{iconNumber}.png")
            pokemonIcon = discord.File(pokemonIconLocation)
            await channel.send(f"A wild {spawnedPokemon} has spawned! Catch it in 60 seconds!", file=pokemonIcon)

            # Start the cooldown period
            catch = False

            # Catch window
            await asyncio.sleep(30)

            #If no one catches the pokemon and the catch window expires, display this
            if spawnedPokemon and not catch:
                await channel.send(f'The wild {spawnedPokemon} escaped!')

            # Choses the next spawn time randomly between 10 minutes and 1 hour
            spawnTimer = random.randint(600, 3600)
            await asyncio.sleep(spawnTimer)

        else:
            # If there's already a spawnedPokemon, wait for the next spawn
            await asyncio.sleep(60)
        spawnedPokemon = None
        catch = False


# Function to get the next Pokémon from the list
def getNextPokemon():

    global pokemonList
    if pokemonList:
        # Select a pokemon based on rarity levels
        selectedPokemon = random.choices(pokemonList, weights, k=1)
        nextPokemon = selectedPokemon[0][1]
        return nextPokemon

    else:
        return None


def savePokedex():
    with open('pokedexdata.json', 'w') as file:
        json.dump(
            pokedex, file,
            indent=4)  # Use json.dump to write the data with proper formatting


def loadPokedex():
    global pokedex
    try:
        with open('pokedexdata.json', "r") as file:
            pokedexData = json.load(
                file)  # Use json.load to load data from the file
        # Update the global pokedex dictionary with the loaded data
        pokedex = pokedexData
    except FileNotFoundError:
        print("Pokedex data file not found. Starting with an empty pokedex.")
        pokedex = {}


async def resetPokedex(message):
    global channelID
    channel = client.get_channel(channelID)
    await channel.send(
        "You have already begun your journey! Would you like to reset your pokedex? Please type $Yes or $No"
    )

    def check(m):
        return m.author == message.author and m.channel == channel

    try:
        response = await client.wait_for('message', check=check, timeout=30)
        if response.content.lower(
        ) == '$yes' and message.author.id == response.author.id:
            pokedex[str(message.author.id)] = {}
            for pokemonEntry in pokemonList:
                pokedex[str(message.author.id)][pokemonEntry[0]] = '???'
            savePokedex()
            loadPokedex()
            await channel.send('You have now obtained a fresh Pokedex!')
        elif response.content.lower(
        ) == '$no' and message.author.id == response.author.id:
            await channel.send("Safe travels!")
        else:
            await channel.send("Invalid response!")
    except asyncio.TimeoutError:
        await channel.send("Time's up. Your Pokedex was not reset.")

def getPokemonDescription(pokemonToGet):
  descriptionURL = 'https://www.pokemon.com/us/pokedex/' + pokemonToGet.lower()
  response = requests.get(descriptionURL)
  if response.status_code != 200:
        print(f"Error: Could not fetch data for {pokemonToGet}")
        return None
  soup = BeautifulSoup(response.text, "html.parser")
  descriptionDiv = soup.find("div", class_="version-descriptions active")
  descriptionY = descriptionDiv.find("p", class_="version-y").get_text().strip()
  descriptionX = descriptionDiv.find("p", class_="version-x").get_text().strip()
  if descriptionY != descriptionX:
    finalDescription = descriptionX + ' ' + descriptionY
  else:
    finalDescription = descriptionY
  return finalDescription


# Run the bot
try:
    client.run(my_secret)
except discord.HTTPException as e:
    if e.status == 429:
        print(
            "The Discord servers denied the connection for making too many requests"
        )
        print(
            "Get help from https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests"
        )
    else:
        raise e
