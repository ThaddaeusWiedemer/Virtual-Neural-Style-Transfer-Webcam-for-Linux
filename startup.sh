#!/bin/bash

# schedule shutdown
shutdown 16:45

# wake up screen
xset -display "$DISPLAY" dpms force on

echo "Starting setup..."

# check that webcam is available
while [ ! -e /dev/video0 ]
do
    echo "No webcam found, please make sure it is plugged in correctly..."
    sleep 2
done
echo "Webcam set up."

# go to stylecam dir
cd /home/tueai/art_mirror/docker
echo "Switched to stylecam dir."

# start a first time to enable the virtual webcam if it's not running
if [ -e /dev/video12 ]
then
    echo "Virtual cam already loaded."
else
    echo "Loading virtual cam..."
    docker-compose -f docker-compose-nvidia.yml run stylecam
    echo "Virtual cam loaded."
fi

# start the program
# runs the stylecam in the docker container and displays the virtual webcam using ffplay
# -vf hflip mirrors the video horizontally
# -fs -video_size 1920x1080 displays the image fullscreen
echo "Starting art mirror..."
docker-compose -f docker-compose-nvidia.yml run stylecam & ffplay -fs -vf hflip -video_size 1920x1080 /dev/video12

# stop the container if the video is closed
# (this ugly workaround just stops all running containers, since the container was started in the background)
docker rm -f $(docker ps -q)