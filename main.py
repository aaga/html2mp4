import numpy as np
import textwrap
import srt
import subprocess
from datetime import timedelta
from bs4 import BeautifulSoup
from moviepy.editor import *
from moviepy.video.tools.drawing import color_gradient
from skimage import transform as tf
from TTS.api import TTS

# BASIC MOVIE RESOLUTION
w = 1280
h = 720
moviesize = w,h

# CINEMATIC RESOLUTION
cw = 1920
ch = 816
cmoviesize = cw,ch

TEMP_AUDIO_FILE = "/tmp/tmp_audio.m4a"
TEMP_VIDEO_FILE = "/tmp/tmp_video.mp4"
TEMP_OPENING_FILE = "/tmp/tmp_opening.mp4"

FPS = 24

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

        make_star_wars_movie(shot_list, dark_mode=True)
        # make_basic_movie(shot_list, with_tts=True)

def make_star_wars_opening(h1scene):
    clips = []
    text = ""
    long_time_ago_text = "A long time ago in an HTML page,\nfar, far away . . . ."
    long_time_ago_clip = TextClip(txt=long_time_ago_text, color="DeepSkyBlue", method="caption", align="center", fontsize=72, font="AppleGothic-Regular", size=cmoviesize)
    long_time_ago_clip = long_time_ago_clip.set_duration(4.3)
    clips.append(long_time_ago_clip)

    # BACKGROUND IMAGE, DARKENED AT 60%
    stars = ImageClip('assets/stars.png')
    stars_darkened = stars.fl_image(lambda pic: (0.6*pic).astype('int16'))

    for shot in h1scene.shots:
        if (shot.tag == "h1"):
            logo_clip = TextClip(txt=shot.get_plain_text().lower(), color="gold", method="caption", align="center", fontsize=120, font="Star-Jedi-Hollow", size=cmoviesize)
            logo_clip = CompositeVideoClip([stars_darkened, logo_clip],size = cmoviesize)
            logo_clip = logo_clip.set_duration(7)
            clips.append(logo_clip)
        else:
            text += ("\n".join(textwrap.wrap(shot.get_plain_text(True), width=45)) + "\n\n")
    if (text[-2:] == "\n\n"):
        text = text[:-2] # Chop off last newlines
    # Add blanks
    text = 13*"\n" + text + 20*"\n" # TODO determine buffers programatically

    # CREATE THE TEXT IMAGE
    clip_txt = TextClip(text, color='gold', align='West',fontsize=48,
    font='Xolonium-Bold', method='label')

    # SCROLL THE TEXT IMAGE BY CROPPING A MOVING AREA
    txt_speed = 40
    fl = lambda gf,t : gf(t)[int(txt_speed*t):int(txt_speed*t)+h,:]
    moving_txt= clip_txt.fl(fl, apply_to=['mask'])

    # ADD A VANISHING EFFECT ON THE TEXT WITH A GRADIENT MASK
    grad = color_gradient(moving_txt.size,p1=(0,2*h/3),p2=(0,h/4),col1=0.0,col2=1.0)
    gradmask = ImageClip(grad,ismask=True)
    fl = lambda pic : np.minimum(pic,gradmask.img)
    moving_txt.mask = moving_txt.mask.fl_image(fl)

    # WARP THE TEXT INTO A TRAPEZOID (PERSPECTIVE EFFECT)
    def trapzWarp(pic,cx,cy,ismask=False):
        """ Complicated function (will be latex packaged as a fx) """
        Y,X = pic.shape[:2]
        src = np.array([[0,0],[X,0],[X,Y],[0,Y]])
        dst = np.array([[cx*X,cy*Y],[(1-cx)*X,cy*Y],[X,Y],[0,Y]])
        tform = tf.ProjectiveTransform()
        tform.estimate(src,dst)
        im = tf.warp(pic, tform.inverse, output_shape=(Y,X))
        return im if ismask else (im*255).astype('uint8')

    fl_im = lambda pic : trapzWarp(pic,0.2,0.3)
    fl_mask = lambda pic : trapzWarp(pic,0.2,0.3, ismask=True)
    warped_txt= moving_txt.fl_image(fl_im)
    warped_txt.mask = warped_txt.mask.fl_image(fl_mask)

    # COMPOSE THE MOVIE
    scroll = CompositeVideoClip([
    stars_darkened,
    warped_txt.set_pos(('center','bottom'))],
    size = cmoviesize)

    scroll = scroll.set_duration(30) # TODO determine duration programatically
    clips.append(scroll)

    final = concatenate_videoclips(clips)
    audio_clip = AudioFileClip("assets/opening.wav")
    audio_clip = audio_clip.set_duration(final.duration)
    final.audio = audio_clip
    final_duration = final.duration

    final.write_videofile(TEMP_OPENING_FILE, codec="libx264", temp_audiofile=TEMP_AUDIO_FILE, remove_temp=True, audio_codec="aac", fps=FPS)

    long_time_ago_clip.close()
    stars.close()
    logo_clip.close()
    clip_txt.close()
    moving_txt.close()
    warped_txt.close()
    scroll.close()
    audio_clip.close()
    final.close()

    return final_duration

def make_star_wars_movie(shot_list, dark_mode = False):
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True)
    clips = []
    subtitles = []
    curr_time = 0.0
    counter = 0

    dt_video, dt_audio, dd_video, dd_audio = None, None, None, None
    if (dark_mode):
        dt_video = VideoFileClip("video_clips/vader.mp4")
        dt_audio = "audio_samples/vader.wav"
        dd_video = VideoFileClip("video_clips/tarkin.mp4")
        dd_audio = "audio_samples/tarkin.wav"
    else:
        dt_video = VideoFileClip("video_clips/luke.mp4")
        dt_audio = "audio_samples/luke.wav"
        dd_video = VideoFileClip("video_clips/c3po.mp4")
        dd_audio = "audio_samples/c3po.wav"

    for scene in shot_list.scenes:
        if (scene.tag == "h1"):
            curr_time += make_star_wars_opening(scene)
        if (scene.tag == "dl"):
            for shot in scene.shots:
                counter += 1
                filepath = "/tmp/" + str(counter) + ".wav"
                clip_to_use = None
                if (shot.tag == "dt"):
                    tts.tts_to_file(text=shot.get_plain_text(), speaker_wav=dt_audio, language="en", file_path=filepath)
                    clip_to_use = dt_video
                else:
                    tts.tts_to_file(text=shot.get_plain_text(), speaker_wav=dd_audio, language="en", file_path=filepath)
                    clip_to_use = dd_video
                audio_clip = AudioFileClip(filepath)
                looped_clip = clip_to_use.loop(duration = audio_clip.duration)
                looped_clip.audio = audio_clip
                clips.append(looped_clip)
                subtitle_text = shot.get_plain_text(True, True)
                subtitles.append(srt.Subtitle(index=counter, start=timedelta(seconds=curr_time), end=timedelta(seconds=curr_time+looped_clip.duration), content=subtitle_text.replace("\n"," ")))
                curr_time += looped_clip.duration

    opening_clip = VideoFileClip(TEMP_OPENING_FILE)
    clips.insert(0, opening_clip)
    final = concatenate_videoclips(clips)
    mp4_filename = "out/" + shot_list.title + ".mp4"
    final.write_videofile(mp4_filename, codec="libx264", temp_audiofile=TEMP_AUDIO_FILE, remove_temp=True, audio_codec="aac", fps=FPS)
    subtitleSRT = srt.compose(subtitles)
    srt_filename = "out/" + shot_list.title + ".srt"
    with open(srt_filename, "w") as text_file:
        text_file.write(subtitleSRT)
    subprocess.run(["ffmpeg", "-i", mp4_filename, "-i", srt_filename, "-c", "copy", "-c:s", "mov_text", TEMP_VIDEO_FILE])
    subprocess.run(["rm", mp4_filename])
    subprocess.run(["mv", TEMP_VIDEO_FILE, mp4_filename])

def make_basic_movie(shot_list, with_tts = False):
    tts = None
    if (with_tts):
        tts = TTS(model_name="tts_models/en/ljspeech/vits", progress_bar=True)
    clips = []
    subtitles = []
    curr_time = 0.0
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
                subtitles.append(srt.Subtitle(index=counter, start=timedelta(seconds=curr_time), end=timedelta(seconds=curr_time+composite_clip.duration), content=speaking_text.replace("\n"," ")))
                curr_time+=composite_clip.duration
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
                        subtitles.append(srt.Subtitle(index=counter, start=timedelta(seconds=curr_time), end=timedelta(seconds=curr_time+composite_clip.duration), content=speaking_text.replace("\n"," ")))
                        curr_time+=composite_clip.duration
                    else:
                        composite_clip = composite_clip.set_duration(5)
                    clips.append(composite_clip)
                    composite = []
                    speaking_text = ""
            
    final = concatenate_videoclips(clips)
    mp4_filename = "out/" + shot_list.title + ".mp4"
    final.write_videofile(mp4_filename, codec="libx264", temp_audiofile=TEMP_AUDIO_FILE, remove_temp=True, audio_codec="aac", fps=5)

    if (tts):
        subtitleSRT = srt.compose(subtitles)
        srt_filename = "out/" + shot_list.title + ".srt"
        with open(srt_filename, "w") as text_file:
            text_file.write(subtitleSRT)
        subprocess.run(["ffmpeg", "-i", mp4_filename, "-i", srt_filename, "-c", "copy", "-c:s", "mov_text", TEMP_VIDEO_FILE])
        subprocess.run(["rm", mp4_filename])
        subprocess.run(["mv", TEMP_VIDEO_FILE, mp4_filename])

if __name__ == "__main__":
    main()
