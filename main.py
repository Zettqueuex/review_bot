import nextcord
from nextcord import Interaction, ButtonStyle, Embed, Activity, ActivityType
from nextcord.ext import commands, tasks
from nextcord.ui import View, TextInput, Button, Modal
import json
from datetime import datetime, timedelta
import pytz
from collections import defaultdict
import os


# อ่านการตั้งค่าจาก config.json
with open('data/config.json') as f:
    config = json.load(f)

# อ่านหรือสร้างไฟล์ delay.json
delay_file_path = 'data/delay.json'
if os.path.exists(delay_file_path):
    with open(delay_file_path, 'r') as f:
        delay_data = json.load(f)
else:
    delay_data = {}

# อ่านหรือสร้างไฟล์ reviews.json
reviews_file_path = 'data/reviews.json'
if os.path.exists(reviews_file_path):
    with open(reviews_file_path, 'r') as f:
        reviews_data = json.load(f)
else:
    reviews_data = {"total": 0, "ratings": {str(i): 0 for i in range(1, 6)}}
# ตรวจสอบและสร้างโครงสร้างข้อมูลที่จำเป็น
if "total" not in reviews_data:
    reviews_data["total"] = 0
if "ratings" not in reviews_data:
    reviews_data["ratings"] = {str(i): 0 for i in range(1, 6)}

intents = nextcord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# บันทึกการตั้งค่าช่องที่ตั้งค่าไว้
settings = {
    "review_channel": config.get("review_channel_id")
}

# ฟังก์ชันสำหรับบันทึกข้อมูล
def save_data():
    with open('delay.json', 'w') as f:
        json.dump(delay_data, f)
    with open('reviews.json', 'w') as f:
        json.dump(reviews_data, f)

# ฟังก์ชันสำหรับนับจำนวนผู้รีวิวทั้งหมด
def count_total_reviewers():
    return reviews_data["total"]

# คำสั่ง slash /setup
@bot.slash_command(name="setup", description="Setup the review system.")
async def setup(interaction: Interaction):
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("คำสั่งนี้สามารถใช้ได้เฉพาะเจ้าของเซิร์ฟเวอร์เท่านั้น", ephemeral=True)
        return

    view = ReviewView()
    embed = Embed(
        title="📝 ระบบรีวิว",
        description="กดปุ่มด้านล่างเพื่อเริ่มการรีวิว\nคุณสามารถรีวิวได้ทุก 24 ชั่วโมง",
        color=nextcord.Color.blue()
    )
    
    # เพิ่มรูปภาพใน Embed
    embed.set_image(url="https://i.pinimg.com/736x/f7/83/67/f78367b9dc1ccf908e6847e1de829e3a.jpg")  # แทนที่ URL_TO_YOUR_IMAGE ด้วย URL ของรูปภาพที่คุณต้องการใช้

    await interaction.response.send_message(embed=embed, view=view)

# คำสั่ง slash /data
@bot.slash_command(name="data", description="แสดงข้อมูลสรุปการรีวิว")
async def data(interaction: Interaction):
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("คำสั่งนี้สามารถใช้ได้เฉพาะเจ้าของเซิร์ฟเวอร์เท่านั้น", ephemeral=True)
        return

    embed = Embed(
        title="📊 สรุปข้อมูลการรีวิว",
        color=nextcord.Color.green()
    )
    
    total_reviews = reviews_data["total"]
    embed.add_field(name="จำนวนรีวิวทั้งหมด", value=str(total_reviews), inline=False)
    
    ratings_summary = "\n".join([f"{i} ดาว: {reviews_data['ratings'][str(i)]} คน" for i in range(1, 6)])
    embed.add_field(name="สรุปคะแนนดาว", value=ratings_summary, inline=False)
    
    await interaction.response.send_message(embed=embed)

class ReviewView(View):
    def __init__(self):
        super().__init__()
        self.add_item(ReviewButton(label="เริ่มรีวิว", style=ButtonStyle.primary, emoji="✍️"))

class ReviewButton(Button):
    def __init__(self, *, label: str, style: ButtonStyle, emoji: str):
        super().__init__(label=label, style=style, emoji=emoji)
    
    async def callback(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        current_time = datetime.now(pytz.timezone('Asia/Bangkok'))
        
        if user_id in delay_data:
            last_review_time = datetime.fromtimestamp(delay_data[user_id], pytz.timezone('Asia/Bangkok'))
            if current_time - last_review_time < timedelta(hours=24):
                time_left = timedelta(hours=24) - (current_time - last_review_time)
                await interaction.response.send_message(f"คุณสามารถรีวิวได้อีกครั้งใน {time_left.seconds // 3600} ชั่วโมง {(time_left.seconds % 3600) // 60} นาที", ephemeral=True)
                return

        await interaction.response.send_modal(ReviewModal())

class ReviewModal(Modal):
    def __init__(self):
        super().__init__(title="กรอกรีวิวและให้คะแนน")
        self.review = TextInput(label="กรุณากรอกรีวิว:", placeholder="รีวิวของคุณ", max_length=200)
        self.rating = TextInput(label="เลือกคะแนนดาว (1-5):", placeholder="1-5", max_length=1)
        self.add_item(self.review)
        self.add_item(self.rating)

    async def callback(self, interaction: Interaction):
        review = self.review.value
        try:
            rating = int(self.rating.value)
            if rating < 1 or rating > 5:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("คะแนนต้องเป็นตัวเลขระหว่าง 1-5", ephemeral=True)
            return

        channel_id = settings.get("review_channel")
        if channel_id:
            channel = bot.get_channel(int(channel_id))
            
            # สร้าง Embed สำหรับรีวิว
            embed = Embed(
                title="🌟 รีวิวใหม่ 🌟",
                description=f"**รีวิว:** {review}\n**คะแนน:** {':star:' * rating}",
                color=nextcord.Color.gold()
            )
            
            # เพิ่มข้อมูลของผู้รีวิว
            user = interaction.user
            embed.set_author(name=f"{user.name}#{user.discriminator}", icon_url=user.display_avatar.url)
            
            # ใช้รูปโปรไฟล์ของผู้รีวิวเป็น thumbnail
            embed.set_thumbnail(url=user.display_avatar.url)
            
            # เพิ่มเวลาที่รีวิว (ไทม์โซนไทย)
            thai_time = datetime.now(pytz.timezone('Asia/Bangkok'))
            embed.set_footer(text=f"รีวิวเมื่อ: {thai_time.strftime('%d %B %Y %H:%M:%S')}")
            
            # เพิ่มลวดลายให้ embed
            embed.add_field(name="💖 ขอบคุณสำหรับรีวิว", value="เราจะนำความคิดเห็นของคุณไปพัฒนาต่อไป", inline=False)

            await channel.send(embed=embed)
            await interaction.response.send_message("🎉 รีวิวของคุณถูกส่งแล้ว! ขอบคุณสำหรับความคิดเห็น", ephemeral=True)

            # บันทึกเวลาการรีวิวล่าสุด
            delay_data[str(interaction.user.id)] = thai_time.timestamp()
            
            # อัปเดตข้อมูลรีวิว
            reviews_data["total"] += 1
            reviews_data["ratings"][str(rating)] += 1
            
            save_data()

            # อัปเดตสถานะของบอท
            await update_bot_status()
        else:
            await interaction.response.send_message("ช่องสำหรับส่งรีวิวยังไม่ได้ตั้งค่า.", ephemeral=True)


@tasks.loop(seconds=10)  # Update status every 10 seconds
async def update_status():
    await update_bot_status()

async def update_bot_status():
    total_reviewers = count_total_reviewers()  # Replace with your function
    await bot.change_presence(
        status=nextcord.Status.idle,  # Change the status here if needed
        activity=Activity(type=ActivityType.watching, name=f"{total_reviewers} คนรีวิว")
    )


def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

@bot.event
async def on_ready():
    clear_terminal()

    # Print bot startup information
    print(f"\033[1;36m{'='*40}\033[0m")  # Print a cyan line
    print(f"\033[1;37mBot is now online!\033[0m")  # Print status in white
    print(f"\033[1;34mLogged in as: {bot.user.name}\033[0m")  # Print bot name in blue
    print(f"\033[1;36m{'='*40}\033[0m")  # Print another cyan line

    # Fetch and print the number of online members
    guilds = bot.guilds
    for guild in guilds:
        online_members = sum(1 for member in guild.members if member.status == nextcord.Status.online)
        print(f"\033[1;33mOnline members in guild '{guild.name}': {online_members}\033[0m")  # Print online members count in yellow

    # Fetch and print the total number of guilds (servers) the bot is in
    total_guilds = len(guilds)
    print(f"\033[1;32mTotal Guilds: {total_guilds}\033[0m")  # Print total guilds in green

    # Print the bot creator's username with additional info
    bot_creator = "phakaphopkub#0"
    print(f"\033[1;35mBot Creator: {bot_creator}\033[0m")  # Print bot creator in purple

    # Start the status update task
    update_status.start()
    await update_bot_status()

bot.run(config['bot_token'])