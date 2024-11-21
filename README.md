[![Image Size](https://img.shields.io/docker/image-size/pixelt/newbaldy?sort=semver&style=for-the-badge)](https://hub.docker.com/layers/pixelt/newbaldy/latest/images/sha256:c37c0315014c85f7c069464fa5e0426d8585341c57b21c1a022fe6486387e776?context=explore)
[![Docker Pulls](https://img.shields.io/docker/pulls/pixelt/newbaldy?style=for-the-badge)](https://hub.docker.com/r/pixelt/newbaldy)
[![License](https://img.shields.io/github/license/UnpixeltGuard/newBaldy?style=for-the-badge)](https://github.com/UnpixeltGuard/newBaldy/blob/master/LICENSE)
[![Version](https://img.shields.io/docker/v/pixelt/newbaldy/latest?style=for-the-badge)](https://hub.docker.com/r/pixelt/newbaldy/tags)
[![Build](https://img.shields.io/github/workflow/status/UnpixeltGuard/newBaldy/Build%20latest%20docker%20image%20for%20JMusicBot?style=for-the-badge)](https://github.com/UnpixeltGuard/newBaldy/actions/workflows/main.yml)
![GitHub last commit](https://img.shields.io/github/last-commit/UnpixeltGuard/newBaldy?style=for-the-badge)

Docker image for my own discord music bot.
Mashed together in Python. Uses Invidious API to bypass YouTube API restrictions. (please support their projects)

Mount your `config.txt` on the path `/app/config.txt`.

```
$ docker run --name jmusicbot -d -v /path/to/config.txt:/app/config.txt:ro \
-v /path/to/downloadfolder:/app/downloads:rw --restart=unless-stopped \
pixelt/newBaldy:latest
```

If you don't already have a `config.txt` either download the template or mount the volume with `:rw`,
this will download the current template from github.

Without own config.txt
```
$ docker run --name jmusicbot -d -v /path/to/config.txt:/app/config.txt:rw \
-v /path/to/downloadfolder:/app/downloads:rw --restart=unless-stopped \
pixelt/newBaldy:latest
```
Command List
```
!play       (song name)
!stop       (stop bot from playing)
!queue      (displays current queue sans the active song)
!skip       (skips to the next song in queue)
!shuffle    (adds 10 random songs to the queue and shuffles it)

as owner
!shutdown   (shuts down bot on backend)
```
