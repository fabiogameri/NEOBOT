import os
import discord
import asyncio
import yt_dlp
from dotenv import load_dotenv
from googleapiclient.discovery import build

def run_bot():
    load_dotenv()
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')  # Set token in .env file
    YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')  # Set YouTube API key in .env file
    intents = discord.Intents.default()
    intents.message_content = True
    discordClient = discord.Client(intents=intents)

    voice_clients = {}
    queues = {}  # Dicionário para armazenar as filas de cada servidor
    yt_dlp_opts = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dlp_opts)

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -filter:a "volume=0.75"'
    }
    
    #API do YouTube para buscar músicas só pelo nome, limitado a cotas diárias (pode não funcionar se chegar nesse limite)
    def search_youtube(query):
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(q=query, part='snippet', type='video')
        response = request.execute()
        if response['items']:
            return 'https://www.youtube.com/watch?v=' + response['items'][0]['id']['videoId']
        else:
            return None

    #Sistema de filas de reprodução
    async def play_next(voice_client):
        if queues[voice_client.guild.id]:
            url = queues[voice_client.guild.id].pop(0)
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            song = data['url']
            title = data['title']
            player = discord.FFmpegOpusAudio(song, **ffmpeg_options)
            voice_client.play(player, after=lambda e: discordClient.loop.create_task(play_next(voice_client)))
            await voice_client.channel.send(f"Tocando agora: **{title}**")
        else:
            await voice_client.disconnect()

    @discordClient.event
    async def on_ready():
        print(f"{discordClient.user} is now running.")

    @discordClient.event
    async def on_message(message):
        if message.content.startswith("!play"):
            # Verifica se algum argumento foi fornecido após o comando !play
            if len(message.content.split()) < 2:
                await message.channel.send("**Digite o nome da música ou URL para tocar!**")
                return
            
            # Verifica se o membro está em um canal de voz
            if message.author.voice is None or message.author.voice.channel is None:
                await message.channel.send("**Você precisa estar em um canal de voz para tocar música!**")
                return
        
            try:
                voice_client = await message.author.voice.channel.connect()
                voice_clients[message.guild.id] = voice_client
                if message.guild.id not in queues:
                    queues[message.guild.id] = []
            except Exception as e:
                print(e)

            search_mode = 'url'  # Default search mode
            query = message.content.split(' ', 1)[1]
            if not query.startswith('http'):
                search_mode = 'search'
                url = search_youtube(query)
            else:
                url = query

            # Verifica se a URL é de uma playlist do YouTube (playlists não são permitidas por sobrecarregar a máquina)
            if 'list=' in url:
                await message.channel.send("**Playlists do YouTube não são permitidas.**")
                return
            
             # Verifica se a URL é de um vídeo do YouTube
            if not url.startswith('https://www.youtube.com/watch?v=') and not url.startswith('https://youtu.be/'):
                await message.channel.send("**Apenas links de vídeos do YouTube são permitidos.**")
                return

            if url:
                if voice_clients[message.guild.id].is_playing() or voice_clients[message.guild.id].is_paused():
                    queues[message.guild.id].append(url)
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
                    title = data['title']
                    await message.channel.send(f"Música **{title}** adicionada à fila.")
                else:
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
                    song = data['url']
                    title = data['title']
                    player = discord.FFmpegOpusAudio(song, **ffmpeg_options)
                    voice_clients[message.guild.id].play(player, after=lambda e: play_next(voice_clients[message.guild.id]))
                    await message.channel.send(f"Tocando agora: **{title}**")
            else:
                await message.channel.send("**Música não encontrada.**")
        
        if message.content.startswith("!stop"):
            try:
                voice_clients[message.guild.id].stop()
                await voice_clients[message.guild.id].disconnect()
                await message.channel.send("**Parando de tocar :(**")
            except Exception as e:
                print(e)
                await message.channel.send("**Não está tocando nada no momento.**")

        if message.content.startswith("!pause"):
            try:
                voice_clients[message.guild.id].pause()
                await message.channel.send("**Música pausada!**")
            except Exception as e:
                print(e)
                await message.channel.send("**Não está tocando nada no momento.**")

        if message.content.startswith("!skip"):
            if message.guild.id in voice_clients and voice_clients[message.guild.id].is_playing():
                voice_clients[message.guild.id].stop()
                await message.channel.send("**Pulando música!**")
                await play_next(voice_clients[message.guild.id])
            else:
                await message.channel.send("**Não está tocando nada no momento.**")

        if message.content.startswith("!resume"):
            try:
                voice_clients[message.guild.id].resume()
                await message.channel.send("**Tocando de volta :D**")
            except Exception as e:
                print(e)
                await message.channel.send("**Não está tocando nada no momento.**")

        if message.content.startswith("!help"):
            await message.channel.send("**Comandos disponíveis:**\n**!play** <nome da música ou URL> \n**!stop** Encerra a música \n**!pause** Pausa a música \n**!resume** Volta a reproduzir a música \n**!skip** Pula a música atual")

    discordClient.run(DISCORD_TOKEN)