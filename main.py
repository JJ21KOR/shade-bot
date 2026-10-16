import asyncio
import json
import os
import random
import secrets
from pathlib import Path
from threading import Thread
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

ROLE_SETTINGS_PATH = Path(__file__).resolve().with_name("role_lottery_config.json")


def load_role_settings() -> dict[str, int]:
    if not ROLE_SETTINGS_PATH.exists():
        return {}

    saved_settings = json.loads(ROLE_SETTINGS_PATH.read_text(encoding="utf-8"))
    if not isinstance(saved_settings, dict):
        raise ValueError("역할 추첨 설정 파일의 형식이 올바르지 않습니다.")

    settings: dict[str, int] = {}
    for guild_id, role_id in saved_settings.items():
        if (
            not isinstance(guild_id, str)
            or not guild_id.isdigit()
            or type(role_id) is not int
            or role_id <= 0
        ):
            raise ValueError("역할 추첨 설정 파일에 올바르지 않은 서버 또는 역할 ID가 있습니다.")
        settings[guild_id] = role_id
    return settings


def save_role_settings(settings: dict[str, int]) -> None:
    temporary_path = ROLE_SETTINGS_PATH.with_name(ROLE_SETTINGS_PATH.name + ".tmp")
    temporary_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    temporary_path.replace(ROLE_SETTINGS_PATH)


def role_has_restricted_permissions(role: discord.Role) -> bool:
    restricted_permissions = (
        "administrator",
        "manage_guild",
        "manage_roles",
        "manage_channels",
        "manage_messages",
        "manage_webhooks",
        "kick_members",
        "ban_members",
        "moderate_members",
        "mention_everyone",
    )
    return any(getattr(role.permissions, name) for name in restricted_permissions)


ROLE_SETTINGS = load_role_settings()

app = Flask('')

@app.route('/')
def home():
    return "SHADE 봇이 24시간 정상 작동 중입니다!"

def run_web_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# 웹 서버 실행 (24시간 유지)
keep_alive()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    if not getattr(bot, "_commands_synced", False):
        try:
            if bot.guilds:
                for guild in bot.guilds:
                    bot.tree.clear_commands(guild=guild)
                    bot.tree.copy_global_to(guild=guild)
                    guild_synced = await bot.tree.sync(guild=guild)
                    print(f"✅ 서버별 슬래시 명령어 {len(guild_synced)}개 동기화 완료")

                # 서버별 명령을 사용해 즉시 반영하고 전역 복사본은 제거해 중복을 막습니다.
                bot.tree.clear_commands(guild=None)
                global_synced = await bot.tree.sync()
                print(f"✅ 전역 중복 명령어 정리 완료 (남은 명령 {len(global_synced)}개)")
            else:
                synced = await bot.tree.sync()
                print(f"✅ 서버 미가입 상태: 전역 슬래시 명령어 {len(synced)}개 동기화 완료")

            bot._commands_synced = True
        except Exception as e:
            print(f"❌ 슬래시 명령어 동기화 실패: {e}")

    print(f"성공적으로 로그인했습니다: {bot.user.name} (ID: {bot.user.id})")
    print("----------------------------------------")

@bot.tree.command(name="인사", description="봇이 사용자에게 반갑습니다 인사합니다.")
async def hello(interaction: discord.Interaction):
    # 가장 기본이 되는 interaction 응답 방식
    await interaction.response.send_message(
        f"안녕하세요, {interaction.user.mention}님! 💖 𝐒𝐇𝐀𝐃𝐄 봇입니다."
    )

@bot.tree.command(name="프로필", description="유저의 프로필 정보를 조회합니다.")
@app_commands.describe(member="정보를 확인할 서버 멤버 (선택사항)")
async def profile(interaction: discord.Interaction, member: discord.Member = None):
    # 멤버 매개변수를 지정하지 않으면 명령어를 실행한 본인을 대상으로 설정
    target = member or interaction.user

    # 예쁜 디자인 카드를 위한 Embed 생성
    embed = discord.Embed(
        title=f"👤 {target.display_name} 님의 프로필",
        color=discord.Color.blue()
    )
    if target.avatar:
        embed.set_thumbnail(url=target.avatar.url)

    embed.add_field(name="유저 이름", value=f"`{target.name}`", inline=True)
    embed.add_field(name="유저 ID", value=f"`{target.id}`", inline=True)
    embed.add_field(
        name="서버 가입일", 
        value=target.joined_at.strftime("%Y-%m-%d %H:%M:%S") if target.joined_at else "정보 없음", 
        inline=False
    )
    embed.set_footer(text=f"요청자: {interaction.user.display_name}")

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="다이스", description="원하는 종류의 주사위를 굴립니다.")
@app_commands.choices(
    dice_type=[
        app_commands.Choice(name="🎲 6면체 주사위 (1~6)", value=6),
        app_commands.Choice(name="🎲 20면체 주사위 (1~20)", value=20),
        app_commands.Choice(name="🎲 100면체 주사위 (1~100)", value=100)
    ]
)
async def roll(interaction: discord.Interaction, dice_type: app_commands.Choice[int]):
    # app_commands.choices를 활용해 사용자가 드롭다운에서 선택하도록 유도
    result = random.randint(1, dice_type.value)
    await interaction.response.send_message(
        f"🎲 **{dice_type.name}**를 굴렸습니다!\n👉 결과: **`{result}`**"
    )

@bot.tree.command(name="비밀메모", description="나에게만 보이는 개인 메모를 작성합니다.")
@app_commands.describe(memo="저장하고 출력할 메모 내용")
async def secret_memo(interaction: discord.Interaction, memo: str):
    # ephemeral=True 옵션으로 본인에게만 보이는 귓속말 응답 전송
    await interaction.response.send_message(
        f"🔒 **[개인 비밀 메모]**\n> {memo}\n\n*이 메시지는 나에게만 보입니다.*",
        ephemeral=True
    )

@bot.tree.command(name="연산", description="시간이 오래 걸리는 작업을 시뮬레이션합니다.")
@app_commands.describe(num="연산할 숫자 입력")
async def calculate(interaction: discord.Interaction, num: int):
    # 3초 이상 소요될 작업은 defer()를 호출해 '생각 중...' 상태로 대기시킵니다.
    await interaction.response.defer(ephemeral=False)

    # 2초 대기 (복잡한 크롤링이나 API 호출 작업 가정)
    await asyncio.sleep(2)
    result = (num * num) + 7

    # defer() 후에는 response.send_message 대신 followup.send를 사용합니다.
    await interaction.followup.send(
        f"⚙️ **계산 완료!**\n입력값 `{num}`의 결과: **`{result}`**"
    )

@bot.tree.command(name="공지사항", description="선택한 채널에 공지사항을 보냅니다.")
@app_commands.describe(
    channel="공지사항을 게시할 텍스트 채널",
    message="보낼 공지 내용 (최대 1900자)",
    ping_everyone="@everyone 알림을 보낼지 선택합니다. 기본값은 꺼짐입니다."
)
async def announcement(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str,
    ping_everyone: bool = False
):
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "이 명령어는 서버 안에서만 사용할 수 있습니다.",
            ephemeral=True
        )
        return

    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "공지사항을 보내려면 서버 관리 권한이 필요합니다.",
            ephemeral=True
        )
        return

    if channel.guild.id != interaction.guild.id:
        await interaction.response.send_message(
            "현재 서버의 채널만 선택할 수 있습니다.",
            ephemeral=True
        )
        return

    message = message.strip()
    if not message:
        await interaction.response.send_message(
            "공지 내용을 입력해 주세요.",
            ephemeral=True
        )
        return

    if len(message) > 1900:
        await interaction.response.send_message(
            "공지 내용은 1900자 이내로 입력해 주세요.",
            ephemeral=True
        )
        return

    bot_member = interaction.guild.get_member(bot.user.id)
    if bot_member is None:
        await interaction.response.send_message(
            "서버에서 봇 정보를 확인할 수 없습니다.",
            ephemeral=True
        )
        return

    bot_permissions = channel.permissions_for(bot_member)
    if not bot_permissions.view_channel or not bot_permissions.send_messages:
        await interaction.response.send_message(
            "봇이 선택한 채널을 보거나 메시지를 보낼 권한이 없습니다.",
            ephemeral=True
        )
        return

    user_permissions = channel.permissions_for(interaction.user)
    if not user_permissions.view_channel or not user_permissions.send_messages:
        await interaction.response.send_message(
            "선택한 채널을 볼 수 있고 메시지를 보낼 수 있는 사용자만 공지할 수 있습니다.",
            ephemeral=True
        )
        return

    if ping_everyone and not bot_permissions.mention_everyone:
        await interaction.response.send_message(
            "봇에 선택한 채널의 `@everyone` 멘션 권한이 없습니다.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    content = f"@everyone\n{message}" if ping_everyone else message
    try:
        await channel.send(
            content,
            allowed_mentions=discord.AllowedMentions(
                everyone=ping_everyone,
                users=False,
                roles=False
            )
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "전송할 수 없습니다. 봇의 채널 메시지 권한을 확인해 주세요.",
            ephemeral=True
        )
        return
    except discord.HTTPException:
        await interaction.followup.send(
            "공지사항 전송에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            ephemeral=True
        )
        return

    ping_status = " (에브리원 핑 포함)" if ping_everyone else ""
    await interaction.followup.send(
        f"공지사항을 {channel.mention}에 전송했습니다{ping_status}.",
        ephemeral=True
    )


@bot.tree.command(name="역할지정", description="이 서버의 0.1% 역할 추첨 보상을 설정합니다.")
@app_commands.describe(role="추첨 당첨 시 지급할 역할")
async def set_lottery_role(interaction: discord.Interaction, role: discord.Role):
    guild = interaction.guild
    if guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "이 명령어는 서버 안에서만 사용할 수 있습니다.",
            ephemeral=True
        )
        return

    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "역할 추첨 설정은 서버 관리자만 변경할 수 있습니다.",
            ephemeral=True
        )
        return

    bot_member = guild.me
    if bot_member is None or not bot_member.guild_permissions.manage_roles:
        await interaction.response.send_message(
            "봇에 역할 관리 권한이 필요합니다.",
            ephemeral=True
        )
        return

    if role.guild.id != guild.id:
        await interaction.response.send_message(
            "현재 서버의 역할만 지정할 수 있습니다.",
            ephemeral=True
        )
        return

    if role.is_default() or role.managed or role >= bot_member.top_role:
        await interaction.response.send_message(
            "봇의 최상위 역할보다 아래에 있고 봇이 관리할 수 있는 역할만 지정할 수 있습니다.",
            ephemeral=True
        )
        return

    if role_has_restricted_permissions(role):
        await interaction.response.send_message(
            "관리자·서버 관리 권한이 포함된 역할은 추첨 보상으로 지정할 수 없습니다.",
            ephemeral=True
        )
        return

    updated_settings = dict(ROLE_SETTINGS)
    updated_settings[str(guild.id)] = role.id
    try:
        save_role_settings(updated_settings)
    except OSError as error:
        print(f"❌ 역할 추첨 설정 저장 실패: {error}")
        await interaction.response.send_message(
            "역할 설정을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            ephemeral=True
        )
        return

    ROLE_SETTINGS.clear()
    ROLE_SETTINGS.update(updated_settings)
    await interaction.response.send_message(
        f"이 서버의 0.1% 추첨 보상을 **{role.name}** 역할로 설정했습니다.",
        ephemeral=True
    )


@bot.tree.command(name="역할추첨", description="0.1% 확률로 이 서버의 설정된 역할을 뽑습니다.")
async def draw_lottery_role(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "이 명령어는 서버 안에서만 사용할 수 있습니다.",
            ephemeral=True
        )
        return

    role_id = ROLE_SETTINGS.get(str(guild.id))
    if role_id is None:
        await interaction.response.send_message(
            "아직 이 서버의 추첨 보상 역할이 설정되지 않았습니다. 관리자에게 `/역할지정`을 요청해 주세요.",
            ephemeral=True
        )
        return

    role = guild.get_role(role_id)
    if role is None:
        await interaction.response.send_message(
            "설정된 역할을 찾을 수 없습니다. 관리자에게 `/역할지정`으로 다시 설정해 달라고 요청해 주세요.",
            ephemeral=True
        )
        return

    if role_has_restricted_permissions(role):
        await interaction.response.send_message(
            "설정된 역할에 관리자 권한이 있어 추첨을 중단했습니다. 관리자가 다른 역할을 지정해야 합니다.",
            ephemeral=True
        )
        return

    if role in interaction.user.roles:
        await interaction.response.send_message(
            "이미 추첨 보상 역할을 가지고 있습니다.",
            ephemeral=True
        )
        return

    bot_member = guild.me
    if (
        bot_member is None
        or not bot_member.guild_permissions.manage_roles
        or role.is_default()
        or role.managed
        or role >= bot_member.top_role
    ):
        await interaction.response.send_message(
            "봇이 해당 역할을 지급할 수 없습니다. 봇의 역할 관리 권한과 역할 순서를 확인해 주세요.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    if secrets.randbelow(1000) != 0:
        await interaction.followup.send(
            "이번에는 당첨되지 않았습니다. 한 번의 명령 실행이 한 번의 0.1% 추첨입니다.",
            ephemeral=True
        )
        return

    try:
        await interaction.user.add_roles(role, reason="0.1% 역할 추첨 당첨")
    except discord.Forbidden:
        await interaction.followup.send(
            "역할을 지급하지 못했습니다. 봇의 역할 관리 권한과 역할 순서를 확인해 주세요.",
            ephemeral=True
        )
        return
    except discord.HTTPException:
        await interaction.followup.send(
            "역할 지급에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            ephemeral=True
        )
        return

    await interaction.followup.send(
        f"축하합니다! **{role.name}** 역할에 당첨되어 지급받았습니다.",
        ephemeral=True
    )


TOKEN = os.environ.get("BOT_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("⚠️ 오류: Replit Secrets 또는 환경 변수에 'BOT_TOKEN'이 설정되지 않았습니다.")