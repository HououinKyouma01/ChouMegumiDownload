# Chou Megumi Download

It's a cross-platform version of a program previously written in C# called [Megumi_Download](https://github.com/HououinKyouma01/Megumi_Download) for Windows, which, in a nutshell, allowed downloading anime episodes from a seedbox, moving them to the appropriate folders, renaming the file (to a system recognized by Kodi's TVDB standard) and automatically replacing various things in the subtitles (order of names, honorifics, etc.). Admittedly, it could be run through Wine on macOS and Linux without any problems, but it had other issues. The most important change is that it has now been rewritten to Python and supports not only parallel downloading of multiple episodes, but also downloading using chunks. Both things speed up the whole process a lot. Everything is configurable. Also, because it is written in Python, it starts natively on any system with a Python interpreter installed. 


## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Advanced Options](#advanced-options)
- [Troubleshooting](#troubleshooting)

## Overview

Megumi Download is a powerful, customizable Python application designed to automate the downloading and organization of anime episodes. It seamlessly integrates with your SFTP server, downloads new episodes, renames them according to your preferences, and even processes subtitles for an enhanced viewing experience.

## Features

- 🚀 **Fast Downloads**: Utilizes chunked and parallel downloading for improved speed
- 🗂️ **Automatic Organization**: Sorts episodes into series and season folders using TVDB standard (maintly for Kodi/Plex)
- 🔄 **SFTP Integration**: Connects to your seedbox or remote server and download episodes automatically
- 🎞️ **Subtitle Processing**: Extracts, modifies, and remuxes subtitles
- ⚙️ **Highly Configurable**: Customize nearly every aspect of the application
- 🖥️ **Cross-Platform**: Works on Windows, macOS, and Linux

## Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/HououinKyouma01/ChouMegumiDownload.git
   cd ChouMegumiDownload
   ```

3. **Install Dependencies**
   ```bash
   pip install paramiko tqdm
   ```

4. **Install MKVToolNix**
   - **Windows**: Download and install from [MKVToolNix's official site](https://mkvtoolnix.download/)
   - **macOS**: Use Homebrew: `brew install mkvtoolnix`
   - **Linux**: Use your package manager, e.g., `sudo apt install mkvtoolnix`

## Configuration

Chou Megumi Download uses three configuration files:

### 1. `config.megumi`

This is the main configuration file. Create it in the same directory as the script with the following options:

```ini
HOST=your.sftp.server
USER=your_username
PASSWORD=your_password
REMOTEPATCH=/path/to/remote/directory/
LOCALPATCH=/path/to/local/anime/directory/
LOCALTEMP=/path/to/temporary/download/directory/
MOVELOCAL=OFF
RENAME=ON
SAVEINFO=ON
CHUNKS=4
USE_CHUNKS=ON
BUFFER_SIZE=1048576
```

- `HOST`, `USER`, `PASSWORD`: Your SFTP server details
- `REMOTEPATCH`: The remote directory to download from
- `LOCALPATCH`: Where to store the downloaded and organized anime
- `LOCALTEMP`: Temporary directory for downloads
- `MOVELOCAL`: Set to "ON" to move local files instead of downloading
- `RENAME`: Set to "ON" to rename files to a standard format
- `SAVEINFO`: Set to "ON" to save original filenames
- `CHUNKS`: Number of chunks for parallel downloading
- `USE_CHUNKS`: Set to "ON" to enable chunked downloading
- `BUFFER_SIZE`: Buffer size for chunk reading (in bytes, can be left as it is)

### 2. `groups.megumi`

List the anime groups you want to download from, one per line:

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

### 3. `serieslist.megumi`

Configure your anime series with the format: `file_name|folder_name|season_number`

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
Hibike! Euphonium S3|Hibike! Euphonium|3
Jiisan Baasan Wakagaeru|Jiisan Baasan Wakagaeru|1
Mushoku Tensei S2|Mushoku Tensei|2
```

## Usage

Run the script with:

```bash
python chou_megumi_download.py
```

The application will:
1. Connect to your SFTP server
2. Download new episodes
3. Organize them into the specified directories
4. Process subtitles if a `replace.txt` file is present in the series directory

## Advanced Options

### Subtitle Replacement

Create a `replace.txt` file in the series directory with replacements (like in example below from Hibike! Euphonium):

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

### Chunked Downloading

Adjust `CHUNKS` and `BUFFER_SIZE` in `config.megumi` to optimize for your network (you can leave it as defeult):

- Increase `CHUNKS` for faster connections
- Adjust `BUFFER_SIZE` based on available memory and network speed

## Troubleshooting

- **SFTP Connection Issues**: Double-check your `HOST`, `USER`, and `PASSWORD` in `config.megumi`
- **Slow Downloads**: Try increasing `CHUNKS` or `BUFFER_SIZE`
- **File Organization Problems**: Ensure your `serieslist.megumi` is correctly formatted
- **MacOS pip command not found**: use
  ```bash
   python3 -m pip install paramiko tqdm
   ```
