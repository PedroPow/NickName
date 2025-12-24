import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from datetime import datetime, timezone
import json
import os
import pytz
from discord import PartialEmoji


# ───────── CONFIG ─────────
TOKEN = "MTQ0NDc4OTI4NTQ0NTMwODYyMA.GNLpNT.M3i7-QQZ0jX5odRpwwfp7gXCwrgg6sKDAnZCK0"
GUILD_ID = 1380696158174974062

CANAL_PAINEL_ID = 1453448841344061544  # canal onde o painel ficará

CARGO_MEMBRO_ID = 1444743630584545522
CARGO_VIP_ID    = 1453440236439998658
CARGO_STAFF_ID  = 1444744188829761737

CANAL_LOG_ID = 1453441190719389838
COOLDOWN_FILE = "cooldown_nick.json"

# ───────── BOT ─────────
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ───────── COOLDOWN ─────────
def carregar_cooldown():
    if not os.path.exists(COOLDOWN_FILE):
        return {}
    with open(COOLDOWN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_cooldown(data):
    with open(COOLDOWN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def inicio_do_dia_utc():
    now = datetime.utcnow()
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

def obter_limite_por_cargo(membro: discord.Member):
    cargos = [c.id for c in membro.roles]

    if CARGO_STAFF_ID in cargos:
        return None
    if CARGO_VIP_ID in cargos:
        return 5
    if CARGO_MEMBRO_ID in cargos:
        return 2
    return 0

# ───────── MODAL ─────────
class AlterarNickModal(Modal, title="Alterar Nick"):
    novo_nick = TextInput(
        label="Novo Nick",
        placeholder="Digite seu novo nickname",
        min_length=2,
        max_length=32
    )

    async def on_submit(self, interaction: discord.Interaction):
        membro = interaction.user
        guild = interaction.guild
        nick_antigo = membro.nick or membro.name

        try:
            await membro.edit(nick=self.novo_nick.value)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Não consigo alterar seu nick.\n"
                "O cargo do bot precisa estar acima do seu.",
                ephemeral=True
            )
            return

        fuso = pytz.timezone("America/Sao_Paulo")
        agora = datetime.now(fuso)

        cooldowns = carregar_cooldown()
        dados = cooldowns.get(str(membro.id), {"usados": 0})
        limite = obter_limite_por_cargo(membro)
        restantes = "∞" if limite is None else max(limite - dados["usados"], 0)

        canal_log = guild.get_channel(CANAL_LOG_ID)
        if canal_log:
            embed = discord.Embed(
                title="📝 Alteração de Nick",
                color=discord.Color.blue(),
                timestamp=agora
            )
            embed.add_field(name="👤 Membro", value=membro.mention, inline=False)
            embed.add_field(name="🔤 Nick Antigo", value=nick_antigo, inline=True)
            embed.add_field(name="🆕 Novo Nick", value=self.novo_nick.value, inline=True)
            embed.add_field(
                name="📊 Uso Diário",
                value=(
                    f"Limite: {limite if limite is not None else '∞'}\n"
                    f"Usados: {dados['usados']}\n"
                    f"Restantes: {restantes}"
                ),
                inline=False
            )
            embed.set_thumbnail(url=membro.display_avatar.url)
            await canal_log.send(embed=embed)

        await interaction.response.send_message(
            "✅ Seu nickname foi alterado com sucesso.",
            ephemeral=True
        )

# ───────── VIEW PERSISTENTE ─────────
def pegar_emoji(guild: discord.Guild, nome: str):
    return discord.utils.get(guild.emojis, name=nome)

class AlterarNickView(View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=None)

        emoji = pegar_emoji(guild, "aguardando")

        botao = Button(
            label="Alterar Nick",
            style=discord.ButtonStyle.secondary,
            custom_id="botao_alterar_nick",
            emoji=emoji  # AQUI SIM FUNCIONA
        )

        botao.callback = self.alterar_nick
        self.add_item(botao)

    async def alterar_nick(self, interaction: discord.Interaction):
        await processar_nick(interaction)

# ───────── LÓGICA CENTRAL ─────────
async def processar_nick(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ Esta função só pode ser usada no servidor.",
            ephemeral=True
        )
        return

    membro = interaction.guild.get_member(interaction.user.id)
    limite = obter_limite_por_cargo(membro)

    if limite == 0:
        await interaction.response.send_message(
            "🚫 Você não possui permissão para alterar seu nick.",
            ephemeral=True
        )
        return

    if limite is not None:
        cooldowns = carregar_cooldown()
        uid = str(membro.id)
        hoje = inicio_do_dia_utc().isoformat()

        dados = cooldowns.get(uid, {"data": hoje, "usados": 0})
        if dados["data"] != hoje:
            dados = {"data": hoje, "usados": 0}

        if dados["usados"] >= limite:
            await interaction.response.send_message(
                "⏳ Você atingiu o limite diário.\n"
                "Tente novamente após **00:00**.",
                ephemeral=True
            )
            return

        dados["usados"] += 1
        cooldowns[uid] = dados
        salvar_cooldown(cooldowns)

    await interaction.response.send_modal(AlterarNickModal())

# ───────── SLASH COMMANDS ─────────
@bot.tree.command(
    name="nick",
    description="Alterar seu nickname",
    guild=discord.Object(id=GUILD_ID)
)
async def slash_nick(interaction: discord.Interaction):
    await processar_nick(interaction)

@bot.tree.command(
    name="nick_info",
    description="Ver informações de troca de nick",
    guild=discord.Object(id=GUILD_ID)
)
async def slash_nick_info(interaction: discord.Interaction):
    membro = interaction.user
    limite = obter_limite_por_cargo(membro)

    cooldowns = carregar_cooldown()
    dados = cooldowns.get(str(membro.id), {"usados": 0})
    restantes = "∞" if limite is None else max(limite - dados["usados"], 0)

    await interaction.response.send_message(
        f"**Informações de Nick**\n\n"
        f"Limite diário: {limite if limite is not None else '∞'}\n"
        f"Usados hoje: {dados['usados']}\n"
        f"Restantes: {restantes}\n"
        f"Reset às 00:00",
        ephemeral=True
    )

# ───────── READY ─────────
@bot.event
async def on_ready():

    guild = bot.get_guild(GUILD_ID)
    canal = guild.get_channel(CANAL_PAINEL_ID)

    if canal is None:
        print("❌ Canal do painel não encontrado.")
        return

    # Apaga mensagens antigas do bot (limpa painéis duplicados)
    async for msg in canal.history(limit=20):
        if msg.author == bot.user:
            await msg.delete()

    embed = discord.Embed(
        title="Alteração de Nick",
        description=(
            "Clique no botão abaixo para alterar **seu próprio nickname**.\n\n"
            "Regras:\n"
            "• Apenas cargos autorizados\n"
            "• Limite diário por cargo\n"
            "• Reset diário às 00:00\n"
            "• Todas as alterações são registradas"
        ),
        color=discord.Color.dark_green(),
    )

    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1447674474697850952/1453465836332257391/Logo_Tropa_do_Trevo_3000_x_3000_px_1.gif?ex=694d8d0b&is=694c3b8b&hm=0139f13d7ee32af7b2d10a062c67f3d3f3dab03098845ec1bab5a28fea543490&")


    view = AlterarNickView(guild)
    await canal.send(embed=embed, view=view)


    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

    print(f"✅ Bot conectado como {bot.user}")


bot.run(TOKEN)
