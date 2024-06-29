# Megumi Download

![Megumi Download Logo](https://via.placeholder.com/150?text=Megumi+Download)

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Advanced Options](#advanced-options)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Overview

Megumi Download is a powerful, customizable Python application designed to automate the downloading and organization of anime episodes. It seamlessly integrates with your SFTP server, downloads new episodes, renames them according to your preferences, and even processes subtitles for an enhanced viewing experience.

## Features

- 🚀 **Fast Downloads**: Utilizes chunked downloading for improved speed
- 🗂️ **Automatic Organization**: Sorts episodes into series and season folders
- 🔄 **SFTP Integration**: Connects to your seedbox or remote server
- 🎞️ **Subtitle Processing**: Extracts, modifies, and remuxes subtitles
- ⚙️ **Highly Configurable**: Customize nearly every aspect of the application
- 🖥️ **Cross-Platform**: Works on Windows, macOS, and Linux

## Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/your-username/megumi-download.git
   cd megumi-download
   ```

2. **Set Up a Virtual Environment (Optional but Recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
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

Megumi Download uses three configuration files:

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
- `BUFFER_SIZE`: Buffer size for chunk reading (in bytes)

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
Kimetsu no Yaiba|Demon Slayer|1
Shingeki no Kyojin|Attack on Titan|4
```

## Usage

Run the script with:

```bash
python megumi_download.py
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
