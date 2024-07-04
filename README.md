# 🌸 Chou Megumi Download 🌸

![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

## 🚀 Supercharge Your Anime Downloads!

It's a cross-platform version of a program previously written in C# called [Megumi_Download](https://github.com/HououinKyouma01/Megumi_Download) for Windows, which, in a nutshell, allowed downloading anime episodes from a seedbox, moving them to the appropriate folders, renaming the file (to a system recognized by Kodi's TVDB standard) and automatically replacing various things in the subtitles (order of names, honorifics, etc.). Admittedly, it could be run through Wine on macOS and Linux without any problems, but it had other issues. The most important change is that it has now been rewritten to Python and supports not only parallel downloading of multiple episodes, but also downloading using chunks. Both things speed up the whole process a lot. Everything is configurable. Also, because it is written in Python, it starts natively on any system with a Python interpreter installed. 

---

## 🌟 Features That'll Make Your Heart Go "DokiDoki!"

- 🎞️ **Subtitle Sorcery**: Extracts, tweaks, and remuxes subtitles like magic! You can replace anything!
- 🚄 **Shinkansen-Fast Downloads**: Parallel and chunked downloading for speed that'll make your head spin!
- 🗂️ **Kodi-Friendly Organization**: Sorts episodes using the TVDB standard, perfect for Kodi and Plex!
- 🔐 **SFTP Superpowers**: Connects to your seedbox faster than you can say "Nani?!"
- ⚙️ **Lab Memeber 001-Level Customization**: Configure every nook and cranny to your liking!
- 🖥️ **Runs Everywhere**: Windows, macOS, Linux – if it can run Python, it can run Chou Megumi Download!

---

## 📦 Installation: Easier Than Making Instant Ramen!

1. **Clone the Repo**
   ```bash
   git clone https://github.com/HououinKyouma01/ChouMegumiDownload.git
   cd ChouMegumiDownload
   ```

2. **Install Dependencies**
   ```bash
   pip install paramiko rich
   ```
   For macOS users experiencing issues:
   ```bash
   python3 -m pip install paramiko rich
   ```

3. **Install MKVToolNix**
   - **Windows**: Grab it from [MKVToolNix's official site](https://mkvtoolnix.download/)
   - **macOS**: `brew install mkvtoolnix`
   - **Linux**: `sudo apt install mkvtoolnix` (or use your distro's package manager)

---

## ⚙️ Configuration: Tailor It to Your Tastes!

### 1. `config.megumi`: The Heart of the Operation

Create this file in the script's directory. Here's a sample to get you started:

```ini
HOST=anime.seedbox.com
USER=otaku_master
PASSWORD=super_secret_password
REMOTEPATCH=/home/user/anime/completed/
LOCALPATCH=/Users/YourName/Movies/Anime/
LOCALTEMP=/Users/YourName/Downloads/AnimeTemp/
MOVELOCAL=OFF
RENAME=ON
SAVEINFO=ON
CHUNKS=4
USE_CHUNKS=OFF
BUFFER_SIZE=1048576
```

### 2. `groups.megumi`: Your Anime Squad

List your favorite release groups:

```
Doki
SNSbu
Nyanpasu
Chihiro
Nii-sama
MTBB
Zafkiel
SubsPlease
```

### 3. `serieslist.megumi`: Your Anime Catalog

Format: `title_in_file_name|series_folder_name|season_number|replace_url`

```
One Room, Hiatari Futsuu, Tenshi-tsuki|One Room, Hiatari Futsuu, Tenshi-tsuki|1
Shuumatsu Train Doko e Iku|Shuumatsu Train Doko e Iku|1
Kami wa Game ni Ueteiru|Kami wa Game ni Ueteiru|1
Spice and Wolf (2024)|Ookami to Koushinryou (2024)|1
Dainanaoji|Tensei shitara Dainana Ouji Datta node, Kimama ni Majutsu wo Kiwamemasu|1
The Dangers in My Heart S2|Boku no Kokoro no Yabai Yatsu|2
Yuru Camp S3|Yuru Camp|3
Hananoi-kun to Koi no Yamai|Hananoi-kun to Koi no Yamai|1
Jellyfish Can't Swim in the Night|Yoru no Kurage wa Oyogenai|1
Hibike! Euphonium S3|Hibike! Euphonium|3|https://example.com/hibike_euphonium_replace.txt
Jiisan Baasan Wakagaeru|Jiisan Baasan Wakagaeru|1
Mushoku Tensei S2|Mushoku Tensei|2
```

Note: The `replace_url` is optional. If provided, the script will automatically download the replace.txt file from the specified URL.

---

## 🎬 Usage: Action!

Fire it up with:

```bash
python chou_megumi_download.py
```

Alternatively, you can download the compiled executable in the "releases" tab

Sit back and watch as Chou Megumi Download:
1. 🔗 Connects to your SFTP server
2. 📥 Downloads fresh episodes
3. 📁 Organizes them into your specified directories
4. 🗣️ Processes subtitles (if `replace.txt` is present)

---

## 🛠️ Tweak your subtitles

### Subtitle Replacement Magic

Create a `replace.txt` in your series folder (for example `C:\Anime\Hibike! Euphonium\Season 3\replace.txt`) and fill it with everthing you want to replace using:

`Old String|New String`

Like in the provided example from Hibike! Euphonium below:

```
Kato|Katou
Yoshi|Yoshii
Yoko|Youko
Yuko|Yuuko
Otaki|Ootaki
Kyoko|Kyouko
Lala|Rara
Shuichi|Shuuichi
Hazuki Katou|Katou Hazuki
Sapphire Kawashima|Kawashima Sapphire
Reina Kousaka|Kousaka Reina
Mayu Kuroe|Kuroe Mayu
Kumiko Oumae|Oumae Kumiko
Kaho Hariya|Hariya Kaho
Kanade Hisaishi|Hisaishi Kanade
Suzume Kamaya|Kamaya Suzume
Tsubame Kamaya|Kamaya Tsubame
Yayoi Kamiishi|Kamiishi Yayoi
Ririka Kenzaki|Kenzaki Ririka
Mirei Suzuki|Suzuki Mirei
Satsuki Suzuki|Suzuki Satsuki
Noboru Taki|Taki Noboru
Shuuichi Tsukamoto|Tsukamoto Shuuichi
Motomu Tsukinaga|Tsukinaga Motomu
Sari Yoshii|Yoshii Sari
Chieri Takahisa|Takahisa Chieri
Hiyoko Ueda|Ueda Hiyoko
Hisae Takano|Takano Hisae
Youko Matsuzaki|Matsuzaki Youko
Aota Maeda|Maeda Aota
Sousuke Maeda|Maeda Sousuke
Michiko Machida|Machida Michiko
Une Kitada|Kitada Une
Motoko Higashiura|Higashiura Motoko
Rairi Hayashi|Hayashi Rairi
Masako Sakai|Sakai Masako
Tairu Kitayama|Kitayama Tairu
Maya Hashida|Hashida Maya
Taku Imura|Imura Taku
Ayako Sakasaki|Sakasaki Ayako
Michiru Hakase|Hakase Michiru
Tomomi Hotei|Hotei Tomomi
Sayaka Takino|Takino Sayaka
Tamari Asakura|Asakura Tamari
Maiya Kikkawa|Kikkawa Maiya
Tsubomi Nakano|Nakano Tsubomi
Sari Takahashi|Takahashi Sari
Meiko Oda|Oda Meiko
Maki Akamatsu|Akamatsu Maki
Sayaka Fukui|Fukui Sayaka
Akiko Yoshizawa|Yoshizawa Akiko
Sumiko Fukamachi|Fukamachi Sumiko
Suguru Takami|Takami Suguru
Kanade Hisaishi|Hisaishi Kanade
Nanami Ootaki|Ootaki Nanami
Kyouko Ayukawa|Ayukawa Kyouko
Babe Uchida|Uchida Babe
Chieri Takahisa|Takahisa Chieri
Hisae Takano|Takano Hisae
Hiyoko Ueda|Ueda Hiyoko
Youko Matsuzaki|Matsuzaki Youko
Miki Katou|Katou Miki
Kiri Matsumoto|Matsumoto Kiri
Machiko Nara|Nara Machiko
Nakaba Hattori|Hattori Nakaba
Narumi Hiraishi|Hiraishi Narumi
Seikoi Ashida|Ashida Seikoi
Kana Etou|Etou Kana
Michiyo Morimoto|Morimoto Michiyo
Junna Inoue|Inoue Junna
Yume Kohinata|Kohinata Yume
Yuuko Yoshikawa|Yoshikawa Yuuko
Natsuki Nakagawa|Nakagawa Natsuki
Nozomi Kasaki|Kasaki Nozomi
Haruna Hosono|Hosono Haruna
Suruga Koteyama|Koteyama Suruga
Aine Kohara|Kohara Aine
Tsumiki Yamane|Yamane Tsumiki
Shiori Hiranuma|Hiranuma Shiori
Eru Kabutodani|Kabutodani Eru
Hibiki Tsuchiya|Tsuchiya Hibiki
Sanae Yashiki|Yashiki Sanae
Rara Hitomi|Hitomi Rara
Chikao Takigawa|Takigawa Chikao
Seiya Suzuki|Suzuki Seiya
Chikai Maki|Maki Chikai
Michie Matsumoto|Matsumoto Michie
Chieri Takashita|Takashita Chieri
Asuka Tanaka|Tanaka Asuka
```
When using a URL for automatic list download, ensure it points to a plain text file with the correct formatting. The script will validate the content before using it for subtitle processing.

### Turbocharge Your Downloads

Adjust these in `config.megumi`:
- Increase `CHUNKS` for faster connections
- Tweak `BUFFER_SIZE` for optimal performance

---

## 🆘 Troubleshooting: When Things Go Yabai

- 🔒 **SFTP Woes**: Double-check your `HOST`, `USER`, and `PASSWORD`
- 🐌 **Snail-Paced Downloads**: Try bumping up `CHUNKS` or `BUFFER_SIZE`
- 🗂️ **Folder Chaos**: Ensure `serieslist.megumi` is formatted correctly
- 🍎 **macOS Hiccups**: Use `python3` instead of `python` for commands

---

Now go forth and download anime and never be like those filthy tourists! 🎌✨
