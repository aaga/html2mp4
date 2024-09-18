from bs4 import BeautifulSoup

from moviepy.editor import *
from moviepy.video.tools.drawing import color_gradient

import torch
from TTS.api import TTS

# Get device
device = "cuda" if torch.cuda.is_available() else "cpu"

# MOVIE RESOLUTION
w = 1280
h = 720
moviesize = w,h

TEMP_AUDIO_FILE = "/tmp/tmp_audio.wav"

class ShotList:
    def __init__(self, title = None):
        self.title = title
        self.scenes = []
    
    def debug_print(self):
        print(self.title)
        for sc in self.scenes:
            print("  ", sc.tag)
            for sh in sc.shots:
                print("    ", sh.tag, ": ", sh.get_plain_text(True))

class Scene:
    def __init__(self, tag = None, name = None):
        self.tag = tag
        self.name = name
        self.shots = []

class Shot:
    def __init__(self, tag = None):
        self.tag = tag
        self.fragments = []
    
    def get_plain_text(self, include_link_decorator = False, include_href = False):
        plain_text = ""
        for frag in self.fragments:
            if (type(frag) is Link):
                if (include_link_decorator):
                    plain_text += ("[" + frag.text + "]")
                else:
                    plain_text += frag.text
                
                if (include_href):
                    plain_text += ("(" + frag.href + ")")
            else:
                plain_text += frag
        return plain_text

class Link:
    def __init__(self, text, href):
        self.text = text
        self.href = href

TAG_SKIP = ["title"]
TAG_NEW_SCENE = ["h1", "dl"]
TAG_NEW_SHOT = ["p", "dt", "dd", "h1"]
TAG_LINK = "a"
TAG_PLAIN = None

shot_list = None
scene = None
shot = None

def layout(element):
    global shot_list, scene, shot
    if (element.name in TAG_SKIP):
        return
    # print("laying out element: ", element.name)
    if (element.name in TAG_NEW_SCENE):
        # Tie off last shot and scene
        if (scene and len(scene.shots) > 0):
            if (shot and len(shot.fragments) > 0):
                scene.shots.append(shot)
            shot_list.scenes.append(scene)
        # Set up next scene and shot
        scene = Scene(element.name)
        shot = Shot()
    if (element.name in TAG_NEW_SHOT):
        # Create a scene if needed
        if (not scene):
            scene = Scene()
        # Tie off last shot
        if (shot and len(shot.fragments) > 0):
            scene.shots.append(shot)
        shot = Shot(element.name)
    if (element.name in [TAG_LINK, TAG_PLAIN]):
        if (not element.string or len(element.string.strip()) == 0):
            # Skip empty element
            return
        # Create a scene and/or shot if needed
        if (not scene):
            scene = Scene()
        if (not shot):
            shot = Shot()
        if (element.name == TAG_LINK):
            frag = Link(element.get_text().replace("\n", " "), element["href"])
        elif (element.name == None):
            # Check for string
            if (not element.string):
                return
            frag = element.get_text().replace("\n", " ")
        shot.fragments.append(frag)
        if (not element.next_sibling):
            scene.shots.append(shot)
            shot = Shot()
        return # Skip the recursion

    # Recurse on child elements, if there are any
    for e in element.contents:
        layout(e)


def main():
    global shot_list
    with open("html_examples/browserjam001_start.html") as fp:
        soup = BeautifulSoup(fp, "html5lib")
        body = soup.body
        title = soup.title.get_text()

        shot_list = ShotList(title)
        layout(body)
        # Tie off last shot and scene
        if (scene and len(scene.shots) > 0):
            if (shot and len(shot.fragments) > 0):
                scene.shots.append(shot)
            shot_list.scenes.append(scene)

        shot_list.debug_print()

        tts = TTS(model_name="tts_models/en/ljspeech/vits", progress_bar=True)

        makeBasicMovie(shot_list, tts)

def makeBasicMovie(shot_list, tts = None):
    clips = []
    counter = 0
    for scene in shot_list.scenes:
        if (scene.tag == "h1"):
            composite = []
            paragraph_text = ""
            speaking_text = ""
            for shot in scene.shots:
                speaking_text += shot.get_plain_text() + "\n"
                if (shot.tag == "h1"):
                    composite.append(TextClip(txt=shot.get_plain_text(True), color="black", method="caption", align="North", fontsize=72, font="Times-New-Roman-Bold", size=moviesize))
                else:
                    paragraph_text += (shot.get_plain_text(True) + "\n\n")
            if (paragraph_text[-2:] == "\n\n"):
                paragraph_text = paragraph_text[:-2] # Chop off last newlines

            composite.append(TextClip(txt=paragraph_text, color="black", method="caption", align="center", fontsize=36, font="Times-New-Roman", size=moviesize))
            composite_clip = CompositeVideoClip(composite, size=moviesize, bg_color=[255,255,255])
            if (tts):
                counter += 1
                filepath = "/tmp/" + str(counter) + ".wav"
                tts.tts_to_file(speaking_text, file_path=filepath)
                audio_clip = AudioFileClip(filepath)
                composite_clip.audio = audio_clip
                composite_clip = composite_clip.set_duration(audio_clip.duration)
            else:
                composite_clip = composite_clip.set_duration(5)
            
            clips.append(composite_clip)
        elif (scene.tag == "dl"):
            composite = []
            speaking_text = ""
            for shot in scene.shots:
                speaking_text += shot.get_plain_text() + "\n"
                if (shot.tag == "dt"):
                    composite.append(TextClip(txt=shot.get_plain_text(True), color="black", method="caption", align="North", fontsize=36, font="Times-New-Roman-Bold", size=moviesize))
                else:
                    composite.append(TextClip(txt=shot.get_plain_text(True), color="black", method="caption", align="center", fontsize=36, font="Times-New-Roman", size=moviesize))
                    composite_clip = CompositeVideoClip(composite, size=moviesize, bg_color=[255,255,255])
                    if (tts):
                        counter += 1
                        filepath = "/tmp/" + str(counter) + ".wav"
                        tts.tts_to_file(speaking_text, file_path=filepath)
                        audio_clip = AudioFileClip(filepath)
                        composite_clip.audio = audio_clip
                        composite_clip = composite_clip.set_duration(audio_clip.duration)
                    else:
                        composite_clip = composite_clip.set_duration(5)
                    clips.append(composite_clip)
                    composite = []
                    speaking_text = ""
            
    final = concatenate_videoclips(clips)
    filename = "out/" + shot_list.title + ".mp4"
    final.write_videofile(filename, codec="libx264", temp_audiofile="/tmp/tmp_audio.m4a", remove_temp=True, audio_codec="aac", fps=5)


if __name__ == "__main__":
    main()
