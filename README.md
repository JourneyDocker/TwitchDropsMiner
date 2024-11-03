# Twitch Drops Miner -- Docker

Thanks to @DevilXD and other contributors from the [original repo](https://github.com/DevilXD/TwitchDropsMiner) for the vast majority of the code.

This application allows you to AFK mine timed Twitch drops, without having to worry about switching channels when the one you were watching goes offline, claiming the drops, or even receiving the stream data itself. This helps both you and Twitch save on bandwidth and hassle. Everyone wins!

### How It Works:

Every several seconds, the application pretends to watch a particular stream by fetching stream metadata - this is enough to advance the drops. Note that this completely bypasses the need to download any actual stream video and sound. To keep the status (ONLINE or OFFLINE) of the channels up-to-date, there's a websocket connection established that receives events about streams going up or down, or updates regarding the current amount of viewers.

### Features:

- Stream-less drop mining - save on bandwidth.
- Game priority and exclusion lists, allowing you to focus on mining what you want, in the order you want, and ignore what you don't want.
- Sharded websocket connection, allowing for tracking up to `(8*50-2)//2=199` channels at the same time.
- Automatic drop campaigns discovery based on linked accounts (requires you to do [account linking](https://www.twitch.tv/drops/campaigns) yourself though)
- Stream tags and drop campaign validation, to ensure you won't end up mining a stream that can't earn you the drop.
- Automatic channel stream switching, when the one you were currently watching goes offline, as well as when a channel streaming a higher priority game goes online.
- Login session is saved in a cookies file, so you don't need to login every time.
- Mining is automatically started as new campaigns appear, and stopped when the last available drops have been mined.

<details>
  <summary><h3>Usage (click for dropdown)</h3></summary>

  ### Docker Usage

  You can use pre-built Docker images to run Twitch Drops Miner:

  1. **Pull the Docker Image:**

     You can choose from two Docker image repositories:

     - From Docker Hub:

       ```sh
       journeyover/twitchdropsminer:main
       ```

     - From GitHub Container Registry:

       ```sh
       ghcr.io/journeydocker/twitchdropsminer:main
       ```

     ### Docker Image Tags

     The `TwitchDropsMiner` Docker image is available in three primary tag formats, each suited to different use cases:

     - **`main` (Continuous Development)**
       - **Description**: The `main` tag is automatically updated to reflect the latest commit on the main branch in GitHub. This image corresponds to the latest development state of `TwitchDropsMiner`.
       - **Usage Consideration**: This tag is not recommended for production use, as it changes frequently and may include untested or unstable updates. Use `main` only if you're contributing to development or need access to the latest features and fixes.
       - **Frequency**: Updated with each new commit to the main branch, making this a rapidly evolving image.

       > **Note**: Pulling the `main` tag may introduce breaking changes or instability, as it represents ongoing development work.

     - **`latest` (Latest Stable Release)**
       - **Description**: This tag points to the most recent stable release of `TwitchDropsMiner`. Unlike `main`, the `latest` tag is only updated with stable, fully-tested versions.
       - **Usage Recommendation**: Use the `latest` tag if you want the most current stable build without specifying a particular version. Ideal for production environments where stability is critical.

       > **Note**: Currently, there is no `latest` tag available. Please check back for updates on the availability of this tag.

     - **`A.B.C.D` (Versioned Release)**
       - **Description**: Versioned tags, such as `A.B.C.D`, are frozen at a specific release version and will not receive updates after publication. Each versioned tag corresponds directly to a released version of `TwitchDropsMiner` on GitHub.
       - **Usage Recommendation**: Use versioned tags when you need consistency and want to avoid updates that might alter functionality. These tags are ideal for production environments requiring fixed versions.

       > **Note**: Currently, there are no versioned tags (e.g., `A.B.C.D`) available. When they are published, each will remain fixed, ensuring a stable and unchanging image for users needing version control.

  2. **Run the Docker Container:**

     Configure the container with environment variables to customize its behavior:

     - **Allow Unlinked Campaigns:** Set the `UNLINKED_CAMPAIGNS` environment variable to `1` to ENABLE mining drops from campaigns that are not linked to your account. By default, this is set to `0` (disabled). Note that even when unlinked campaigns are enabled, the application will still consider your priority list, so ensure the desired game is included in your priority list.

     - **Priority Mode:** Set the `PRIORITY_MODE` environment variable to one of the following values to determine how the miner prioritizes campaigns:
       - `0`: **Use the priority list directly.** Campaigns are mined in the exact order they appear in the priority list, without additional prioritization.
       - `1` (default): **Prioritize based on time-to-end.** Campaigns in the priority list are mined based on how soon they are ending, with those nearing their end being prioritized higher.
       - `2`: **Optimize by time ratio.** Campaigns are prioritized according to the ratio of elapsed time to remaining time, aiming to mine campaigns that are ending soonest more accurately.

     Example of running the container with these environment variables:

     ```sh
     docker run -itd \
       --init \
       --pull=always \
       --restart=always \
       -e UNLINKED_CAMPAIGNS=1 \
       -e PRIORITY_MODE=1 \
       -v ./cookies.jar:/TwitchDropsMiner/cookies.jar \
       -v ./settings.json:/TwitchDropsMiner/settings.json \
       -v /etc/localtime:/etc/localtime:ro \
       --name twitch_drops_miner \
       ghcr.io/journeyover/twitchdropsminer
     ```

     ### Docker Compose Example

     To simplify running `TwitchDropsMiner`, you can use Docker Compose with the following configuration. Create a `docker-compose.yml` file in your working directory:

     ```yaml
     version: '3.8'

     services:
       twitchdropsminer:
         image: ghcr.io/journeyover/twitchdropsminer:latest
         container_name: twitch_drops_miner
         restart: always
         environment:
           UNLINKED_CAMPAIGNS: "0"   # Set to "1" to enable unlinked campaigns mining
           PRIORITY_MODE: "1"        # Set priority mode (0, 1, or 2)
         volumes:
           - ./cookies.jar:/TwitchDropsMiner/cookies.jar
           - ./settings.json:/TwitchDropsMiner/settings.json
           - /etc/localtime:/etc/localtime:ro
     ```

     After creating the `docker-compose.yml` file, start the container with:

     ```sh
     docker-compose up -d
     ```

  - **Docker Considerations:** If you are running the application in Docker, remember to shut down the container before making changes directly to the `settings.json` file.

### Manual Usage:

- Download and unzip [the latest release](https://github.com/JourneyDocker/TwitchDropsMiner/releases).
- Run it and login/connect the miner to your Twitch account by using the in-app login form.
- After a successful login, the app should fetch a list of all available campaigns and games you can mine drops for - you can then select and add games of choice to the Priority List available on the Settings tab, and then press on the `Reload` button to start processing. It will fetch a list of all applicable streams it can watch, and start mining right away. You can also manually switch to a different channel as needed.
- Make sure to link your Twitch account to game accounts on the [campaigns page](https://www.twitch.tv/drops/campaigns), to enable more games to be mined.

</details>

### Pictures:

![Main](https://user-images.githubusercontent.com/4180725/164298155-c0880ad7-6423-4419-8d73-f3c053730a1b.png)
![Inventory](https://user-images.githubusercontent.com/4180725/164298315-81cae0d2-24a4-4822-a056-154fd763c284.png)
![Settings](https://user-images.githubusercontent.com/4180725/164298391-b13ad40d-3881-436c-8d4c-34e2bbe33a78.png)

### Notes:

> [!WARNING]
> Requires Python 3.10 or higher.

> [!CAUTION]
> Persistent cookies will be stored in the `cookies.jar` file, from which the authorization (login) information will be restored on each subsequent run. Make sure to keep your cookies file safe, as the authorization information it stores can give another person access to your Twitch account.

> [!IMPORTANT]
> Successfully logging into your Twitch account in the application may cause Twitch to send you a "New Login" notification email. This is normal - you can verify that it comes from your own IP address. The detected browser during the login will be "Chrome", as that's what the miner currently presents itself as internally.

> [!NOTE]
> The miner uses an OAuth login flow to let you authorize it to use your account. This is done by entering the code printed in the miner's Output window on the [Twitch device activation page](https://www.twitch.tv/activate). If you'd ever wish to unlink the miner from your Twitch account, head over to the [connections page,](https://www.twitch.tv/settings/connections) where you should be able to find the miner in the "Other connections" section. It will be listed as "Twitch Mobile Web". Simply click on "Disconnect" to remove the link and invalidate the authorization token.

> [!NOTE]
> The time remaining timer always countdowns a single minute and then stops - it is then restarted only after the application redetermines the remaining time. This "redetermination" can happen at any time Twitch decides to report on the drop's progress, but not later than 20 seconds after the timer reaches zero. The seconds timer is only an approximation and does not represent nor affect actual mining speed. The time variations are due to Twitch sometimes not reporting drop progress at all, or reporting progress for the wrong drop - these cases have all been accounted for in the application though.

### Notes about the Windows build:

- To achieve a portable-executable format, the application is packaged with PyInstaller into an `EXE`. Some non-mainstream antivirus engines might report the packaged executable as a trojan, because PyInstaller has been used by others to package malicious Python code in the past. These reports can be safely ignored. If you absolutely do not trust the executable, you'll have to install Python yourself and run everything from source.
- The executable uses the `%TEMP%` directory for temporary runtime storage of files, that don't need to be exposed to the user (like compiled code and translation files). For persistent storage, the directory the executable resides in is used instead.
- The autostart feature is implemented as a registry entry to the current user's (`HKCU`) autostart key. It is only altered when toggling the respective option. If you relocate the app to a different directory, the autostart feature will stop working, until you toggle the option off and back on again

### Notes about the Linux build:

- The Linux app is built and distributed using two distinct portable-executable formats: [AppImage](https://appimage.org/) and [PyInstaller](https://pyinstaller.org/).
- There are no major differences between the two formats, but if you're looking for a recommendation, use the AppImage.
- The Linux app should work out of the box on any modern distribution, as long as it has `glibc>=2.31` (PyInstaller package) or `glibc>=2.35` (AppImage package), plus a working display server.
- Every feature of the app is expected to work on Linux just as well as it does on Windows. If you find something that's broken, please [open a new issue](https://github.com/DevilXD/TwitchDropsMiner/issues/new).
- The size of the Linux app is significantly larger than the Windows app due to the inclusion of the `gtk3` library (and its dependencies), which is required for proper system tray/notifications support.
- As an alternative to the native Linux app, you can run the Windows app via [Wine](https://www.winehq.org/) instead. It works really well!

### Advanced Usage:

If you'd be interested in running the latest master from source or building your own executable, see the wiki page explaining how to do so: https://github.com/DevilXD/TwitchDropsMiner/wiki/Setting-up-the-environment,-building-and-running

### Support

<div align="center">

[![Buy me a coffee](https://i.imgur.com/cL95gzE.png)](
    https://www.buymeacoffee.com/DevilXD
)
[![Support me on Patreon](https://i.imgur.com/Mdkb9jq.png)](
    https://www.patreon.com/bePatron?u=26937862
)

</div>

### Project goals:

Twitch Drops Miner (TDM for short) has been designed with a couple of simple goals in mind. These are, specifically:

- Twitch Drops oriented - it's in the name. That's what I made it for.
- Easy to use for an average person. Includes a nice looking GUI and is packaged as a ready-to-go executable, without requiring an existing Python installation to work.
- Intended as a helper tool that starts together with your PC, runs in the background through out the day, and then closes together with your PC shutting down at the end of the day. If it can run continuously for 24 hours at minimum, and not run into any errors, I'd call that good enough already.
- Requiring a minimum amount of attention during operation - check it once or twice through out the day to see if everything's fine with it.
- Underlying service friendly - the amount of interactions done with the Twitch site is kept to the minimum required for reliable operation, at a level achievable by a diligent site user.

TDM is not intended for/as:

- Mining channel points - again, it's about the drops: only.
- Mining anything else besides Twitch drops - no, I won't be adding support for a random 3rd party site that also happens to rely on watching Twitch streams.
- Unattended operation: worst case scenario, it'll stop working and you'll hopefully notice that at some point. Hopefully.
- 100% uptime application, due to the underlying nature of it, expect fatal errors to happen every so often.
- Being used with more than one managed account.

This means that features such as:

- Anything that increases the site processing load caused by the application.
- Any form of additional notifications system (email, webhook, etc.), beyond what's already implemented.

..., are most likely not going to be a feature, ever. You're welcome to search through the existing issues to comment on your point of view on the relevant matters, where applicable. Otherwise, most of the new issues that go against these goals will be closed and the user will be pointed to this paragraph.

For more context about these goals, please check out these issues: [#161](https://github.com/DevilXD/TwitchDropsMiner/issues/161), [#105](https://github.com/DevilXD/TwitchDropsMiner/issues/105), [#84](https://github.com/DevilXD/TwitchDropsMiner/issues/84)

### Credits:

<!---
Note: When adding a new credits line below, please add two spaces at the end of the previous line,
if they aren't already there. Doing so ensures proper markdown rendering on Github.

• Last line can have them omitted.
• Please ensure your editor won't trim the spaces upon saving the file.
• Please leave a single empty new line at the end of the file.
-->

| Contributor            | Translation                                      |
|------------------------|--------------------------------------------------|
| @Suz1e                 | Chinese (Simplified) - 简体中文                   |
| @wwj010                | Chinese (Simplified) - Corrections and Revisions |
| @nwvh                  | Czech - Čeština                                  |
| @ThisIsCyreX           | German - Deutsch                                 |
| @Shofuu                | Spanish - Español                                |
| @zarigata              | Portuguese - Português                           |
| @alikdb                | Turkish - Türkçe                                 |
| @roobini-gamer         | French - Français                                |
| @Sergo1217             | Russian - Русский                                |
| @Ricky103403           | Chinese (Traditional) - 繁體中文                  |
| @Patriot99 & @DevilXD  | Polish - Polski                                  |
| @Nollasko              | Ukrainian - Українська                           |
| @casungo               | Italian - Italiano                               |
| @Bamboozul             | Arabic - العربية                                 |
| @Kjerne                | Danish - Dansk                                   |
| @ShimadaNanaki         | Japanese - 日本語                                 |
