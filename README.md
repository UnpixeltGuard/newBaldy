[![Image Size](https://img.shields.io/docker/image-size/pixelt/newbaldy?sort=semver&style=for-the-badge)](https://hub.docker.com/layers/pixelt/newbaldy/latest/images/sha256:c37c0315014c85f7c069464fa5e0426d8585341c57b21c1a022fe6486387e776?context=explore)
[![Docker Pulls](https://img.shields.io/docker/pulls/pixelt/newbaldy?style=for-the-badge)](https://hub.docker.com/r/pixelt/newbaldy)
[![License](https://img.shields.io/github/license/UnpixeltGuard/newBaldy?style=for-the-badge)](https://github.com/UnpixeltGuard/newBaldy/blob/master/LICENSE)
[![Version](https://img.shields.io/docker/v/pixelt/newbaldy/latest?style=for-the-badge)](https://hub.docker.com/r/pixelt/newbaldy/tags)
![GitHub last commit](https://img.shields.io/github/last-commit/UnpixeltGuard/newBaldy?style=for-the-badge)

[![Build](https://github.com/UnpixeltGuard/newBaldy/actions/workflows/docker.yml/badge.svg)](https://github.com/UnpixeltGuard/newBaldy/actions/workflows/docker.yml)

My own small discord music bot for personal use.
Mashed together in Python. Needs a Youtube Data v3 API Key. (usually ran into issues with api requests without)

Mount your `config.txt` on the path `/app/.env`.

```
$ docker run --name baldbot -d -v /path/to/config.txt:/app/.env:ro \
-v /path/to/downloadfolder:/app/downloads:rw \
-v /path/to/index:/app/index:rw --restart=unless-stopped \
pixelt/newBaldy:latest
```

If you don't already have a `config.txt` either download the template or mount the volume with `:rw`,
this will download the current template from github.

Without own config.txt
```
$ docker run --name baldbot -d -v /path/to/config.txt:/app/.env:rw \
-v /path/to/downloadfolder:/app/downloads:rw \
-v /path/to/index:/app/index:rw --restart=unless-stopped \
pixelt/newBaldy:latest
```
Command List
```
!search     (song name)
!play       (song name)
!stop       (stop bot from playing)
!queue      (displays current queue sans the active song)
!skip       (skips to the next song in queue)
!shuffle    (adds 10 random songs to the queue and shuffles it)
!library    (shows all currently downloaded songs) (allows to search for downloaded songs by title)

as owner
!shutdown   (shuts down bot on backend)
!remove     (with the id of the video that is to be removed from the library and downloadfolder)
```
