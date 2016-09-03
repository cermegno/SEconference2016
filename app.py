#import uuid
import time
import os, sys
import re
import boto
import redis
from flask import Flask, render_template, redirect, request, url_for, make_response
from werkzeug import secure_filename
from PIL import Image, ImageOps
#import hashlib
import json

VCAP_SERVICES = json.loads(os.environ['VCAP_SERVICES'])
CREDENTIALS = VCAP_SERVICES["rediscloud"][0]["credentials"]
r = redis.Redis(host=CREDENTIALS["hostname"], port=CREDENTIALS["port"], password=CREDENTIALS["password"])
bname = os.environ['bucket']
ecs_access_key_id = os.environ['ECS_access_key'] 
ecs_secret_key = os.environ['ECS_secret']
ecs_host = os.environ['ECS_host']
access_url = os.environ['object_access_URL']
size = 150, 150
epoch_offset = 36000 #The offset in seconds with Sydney

#boto.set_stream_logger('boto')

#####  ECS version  #####
session = boto.connect_s3(aws_access_key_id=ecs_access_key_id, \
                          aws_secret_access_key=ecs_secret_key, \
                          host=ecs_host)  

#####  AWS S3 version  #####
##session = boto.connect_s3(ecs_access_key_id, ecs_secret_key)

b = session.get_bucket(bname)
##print "Redis connection is: " + str(r)
##print "ECS connection is: " + str(session)
##print "Bucket is: " + str(b)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = set(['jpg', 'jpeg', 'JPG', 'JPEG'])

#Read the seed file and populate Redis. It could be part of an init script
f = open('sessions.txt') #Fields separated by ";" to allow for "," in description field
snames = []
stimes = []
session_list = f.readlines()
f.close()
i = 0

for each_session in session_list:
    i += 1
    newsession = "session" + str(i)
    (c, t, p, e, ro, d) = each_session.split(';')
    r.hmset(newsession,{'code':c.strip(),'title':t.strip(),'presenter':p.strip(),'epoch':e.strip(),'room':ro.strip(),'description':d.strip()})
    snames.append(t)
    stimes.append(e)

print stimes
if not r.get("ucounter"):
    r.set("ucounter","0")

@app.route('/')
def menu():
    global stimes
    global r
    r.incr('hitcounter')
    photocount = r.get("pcounter")
    print "Amount of photos :", photocount
    reviewcount = r.get("rcounter")
    print "Amount of reviews : ", reviewcount
    
    current = int(time.time())-time.timezone
    print current
    anchor = 0
    for t in stimes:
        if current > int(t):
            anchor = t
       
    print "Anchor is " + str(anchor)

    uuid = request.cookies.get('uuid')
    if not uuid:
        print "uuid cookie was not present"
        uuid = r.incr('ucounter')
    print "uuid now is :", uuid
    usercount = r.get('ucounter')
    print "User counter : ", usercount
    resp = make_response(render_template('main_menu.html', anchor=anchor, reviews=reviewcount, photos=photocount, ucount=usercount))
    resp.set_cookie('uuid',str(uuid), max_age=604800)
    return resp

@app.route('/single.html')
def single():
    global r
    r.incr('hitcounter')
    choices = ""
    i = 0
    while i < len (r.keys('session*')):
        n = snames[i]
        i +=1
        s = "session" + str(i)

        newchoice = """
                <option value="{}">{} - {}</option>""".format(n,n,r.hget(s,'presenter'))
        choices = choices + newchoice

    uuid = request.cookies.get('uuid')
    if not uuid:
        print "uuid cookie was not present"
        uuid = r.incr('ucounter')
    print "uuid now is :", uuid
    usercount = r.get('ucounter')
    print "User counter : ", usercount
    resp = make_response(render_template('form_single.html',choices=choices))
    resp.set_cookie('uuid',str(uuid), max_age=604800)
    return resp

@app.route('/sthankyou.html', methods=['POST'])
def sthankyou():
    global r
    r.incr('hitcounter')
    s = request.form['session']
    c = request.form['content']
    p = request.form['presenter']    
    uuid = request.cookies.get('uuid')

    Counter = r.incr('rcounter')
    print "the counter is now: ", Counter
    newreview = 'review' + str(Counter)
    print "Lets create Redis hash: " , newreview
    r.hmset(newreview,{'session':s,'content':c,'presenter':p, 'uuid':uuid})

    return render_template('form_action.html', session=s, content=c, presenter=p)

@app.route('/program.html')
def program():
    global r
    r.incr('hitcounter')
    allsessions = ""

    i = 0
    while i < len (r.keys('session*')):
        i +=1
        each_session = "session" + str(i)
        epoch = r.hget(each_session,'epoch')
        room = r.hget(each_session,'room')
        title = r.hget(each_session,'title')
        presenter = r.hget(each_session,'presenter')
        description = r.hget(each_session,'description')
        # time.timezone doesn't seem to work in PCF, so I use a constant
        human_time = time.strftime("%d-%b %H:%M",time.gmtime(int(epoch)+epoch_offset))

        thissession = '''
            <a name="{}"></a>
            <div class="container">
              <div class="content">
                    <table class="program">
                    <tr><td>{} in {}
                    <tr><td><b>{}
                    <tr><td><i>by {}
                    <tr><td>{}
                    </table>
              </div>
            </div>
            '''.format(epoch,human_time,room,title,presenter,description)

        allsessions = allsessions + thissession

    beginning = """
        <html>
        <head>
            <link rel=stylesheet type=text/css href="/static/style.css">
			<meta name="viewport" content="width=410, initial-scale=0.90">
        </head>
        <body>
            <div class="container">
              <div class="content">
                <h1>Event Program</h1>
              </div>
            </div>
        """
    theend = '''
        </body>
        </html>
        '''
    return beginning + allsessions + theend

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']

@app.route('/upload_photo.html')
def index():
    global r
    r.incr('hitcounter')
    return render_template('upload_photo.html')


@app.route('/upload', methods=['POST'])
def upload():
    global size
    global b
    global r
	
    file = request.files['file']
    if file and allowed_file(file.filename):
        # Make the filename safe, remove unsupported chars
        filename = secure_filename(file.filename)
        justname = filename.rsplit(".",1)[0]
        justname = justname + str (int (time.time() * 1000))
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        thumbfile = justname + "-thumb.jpg"
        try:
            im = Image.open("uploads/" + filename)
            thumb = ImageOps.fit(im, size, Image.ANTIALIAS)
            thumb.save("uploads/" + thumbfile, "JPEG")
            im.close()
            thumb.close()
        except IOError:
            print "cannot create thumbnail for", filename

        print "Uploading " + filename + " as key " + justname
        k = b.new_key(justname)
        k.set_contents_from_filename("uploads/" + filename)
        k.set_acl('public-read')
		
        thumbkey = justname + "-thumb"
        print "Uploading thumb " + thumbfile + " as key " + thumbkey
        k = b.new_key(thumbkey)
        k.set_contents_from_filename("uploads/" + thumbfile)
        k.set_acl('public-read')

        os.remove("uploads/" + filename)
        os.remove("uploads/" + thumbfile)

        uuid = request.cookies.get('uuid')
        Counter = r.incr('pcounter')
        print "the photo counter is now: ", Counter
        newphoto = 'photo' + str(Counter)
        print "Lets create Redis hash: " , newphoto
        r.hmset(newphoto,{'name':justname, 'uuid':uuid})
        return"""
        <html>
          <head>
            <link rel=stylesheet type=text/css href="/static/style.css">
            <meta name="viewport" content="width=410, initial-scale=0.90">
          </head>
          <body>
            <div class="container">
            <div class="content">
            <h3>Thanks for your photo</h3>
            <a href="/"><h3>Back to main menu</h3></a>
        <img src="/static/logo.png" width="270" />
	"""
    
@app.route('/showphotos.html')
def photos():
    global r
    global bname
    r.incr('hitcounter')
    photocount = r.get("pcounter")

    filetable = """
        <html>
          <head>
            <link rel=stylesheet type=text/css href="static/style.css">
            <meta name="viewport" content="width=410, initial-scale=0.90">

          </head>
          <body>
            <div class="container">
            <div class="content">
            <img src="static/logo.png" width="270" />
            <h2>Total photos uploaded: {} </h2>
            <a href="/"><h3>Back to main menu</h3></a>
    """.format(photocount)

    for each_photo in r.keys('photo*'):
        print each_photo
        filetable = filetable + \
                    "<a href=\"http://" + access_url + "/" + bname + "/" \
                    + r.hget(each_photo,'name') + "\" target=\"_blank\">" \
                    + "<img src=\"http://" + access_url + "/" + bname + "/" \
                    + r.hget(each_photo,'name') + "-thumb\"></a>"

    return filetable

#################################################################
## Two ways of accessing objects in ECS
## http://bucketname.namespace.public.ecstestdrive.com/objectname
## or
## http://namespace.public.ecstestdrive.com/bucketname/objectname
## We are using the second one so that you change only an env var
## to switch between AWS and ECS 

@app.route('/floorplan')
def floorplan():
    global r
    r.incr('hitcounter')
    resp = make_response(render_template('floorplan.html'))
    return resp

@app.route('/survey')
def survey():
    global r
    r.incr('hitcounter')
    resp = make_response(render_template('survey.html'))
    return resp

@app.route('/suthankyou.html', methods=['POST'])
def suthankyou():
    global r
    r.incr('hitcounter')

    uuid = request.cookies.get('uuid')
    if not uuid:
        uuid = 0
    outstring = "uuid:" + str(uuid) + ";"

    allvalues = sorted(request.form.items())
    for key,value in allvalues:
        outstring += key + ":" + value + ";"
    print outstring
    
    Counter = r.incr('scounter')
    print "the counter is now: ", Counter
    newsurvey = 'survey' + str(Counter)
    print "Lets create Redis hash: " , newsurvey
    r.hmset(newsurvey,{'review_string':outstring})
    
    resp = make_response(render_template('survey_action.html'))
    return resp

##########################################
# This section contains hidden admin links
	
##@app.route('/kdump')
##def kdump():
##    global session
##    print session.get_all_buckets()  
##    for bucket in session.get_all_buckets():
##        print "In bucket: " + bucket.name
##        for object in bucket.list():
##            print(object.key)
##    return "Keys have been dumped in the console"

@app.route('/rdump')
def rdump():
    global r
    output = "session; content; presenter; uuid<br>"
    for each_review in r.keys('review*'):
        output = output + "%s; %s; %s; %s<br>" % (r.hget(each_review,'session'), \
                                              r.hget(each_review,'content'), \
                                              r.hget(each_review,'presenter'), \
                                              r.hget(each_review,'uuid'))

    return output

@app.route('/pdump')
def pdump():
    global r
    output = "photo, uuid<br>"
    for each_photo in r.keys('photo*'):
        output = output + "%s, %s<br>" % (r.hget(each_photo,'name'), \
                                              r.hget(each_photo,'uuid'))

@app.route('/sdump')
def sdump():
    global r

    output = ""
    for each_survey in r.keys('survey*'):
        output += "%s<br>" % (r.hget(each_survey,'review_string'))

    return output

											  
@app.route('/stats')
def hitdump():
    global r
    hits = r.get('hitcounter')
    visitors = r.get('ucounter')
    reviews = len(r.keys('review*'))
    surveys = len(r.keys('survey*'))
    resp = "Total pageviews: " + str(hits) + "<br>Unique visitors: " + str(visitors) + "<br>Total reviews: " \
           + str(reviews) + "<br>Surveys received: " + str(surveys)
    return resp

@app.route('/sessionrankings')
def sessionrankings():
#########################################################
# A disctionary might not be the best choice for this but
# this is will be run only once at the end of the event
    global r
    rankings = {}

    for each_session in r.keys('session*'):
        code = str(r.hget(each_session,'code'))
        rankings[code] = [code,r.hget(each_session,'title'),0,0,0]

    for each_review in r.keys('review*'):
        this_session = r.hget(each_review,'session')

        for key in rankings:
            if this_session == rankings[key][1]:
##                print "session match: " + this_session
##                print  "Presenter: " + r.hget(each_review,'presenter') + "  Content: " + r.hget(each_review,'content')
                newpresenter = float(r.hget(each_review,'presenter'))
                newcontent = float(r.hget(each_review,'content'))
                presenteravg = float(rankings[key][2])
                contentavg = float(rankings[key][3])
                numreviews = int(rankings[key][4])
                rankings[key][2] = ((presenteravg * numreviews) + newpresenter)/(numreviews + 1)
                rankings[key][3] = ((contentavg * numreviews) + newcontent)/(numreviews + 1)
                rankings[key][4] += 1

    resp ="Session code;Title;Presenter avg;Content avg;Number of reviews<br>\n"
    for key in rankings:
        newranking = rankings[key][0] + ";" + rankings[key][1] + ";" + str(round(rankings[key][2],1)) \
                     + ";" + str(round(rankings[key][3],1)) + ";" + str(rankings[key][4]) + "<br>\n"
        resp += newranking
    
    return resp

@app.route('/uid')
def uid():
    uuid = request.cookies.get('uuid')
    return "Your user ID is : " + uuid

if __name__ == "__main__":
	app.run(debug=False, host='0.0.0.0', \
                port=int(os.getenv('PORT', '5000')), threaded=True)
