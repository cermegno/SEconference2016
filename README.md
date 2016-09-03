# SE Conference app v1.1
Companion app for EMC Australian SE Conference 2016

# SUMMARY
Flask web app with Redis backend and EMC's ECS S3 object store.

# FUNCTIONALITY
* Displays the conference program/agenda
* Scrolls down the program to the last session before current time
* Allows attendees to review the different sessions in the conference in terms of presenter and content
* Allows users to upload their favourite photos of the conference (restricted to jpg)
* Allows users to browse uploaded photos
* Contains an event survey to provide demographic stats and/or feedback

It provides is also the following hidden admin functionality:

* Produces a ranking of all sessions with average scores for presenter and content as well as the amount of reviews
* Allows event admins to dump all the reviews in a ";" separated format for analysis. The cookie ID is provided to help eliminate duplicates
* Dumps all the survey responses. The cookie ID is provided to help eliminate duplicates
* Provides stats such as number of pageviews and unique visitors
* Allows users to display their uid. This could be use to identify the owner of an uploaded photo as the winner of a competition  

# REQUIREMENTS
* Cloud Foundry (the syntax to grab Redis credentials will work with CF environment variables)
* Flask directories
   * static (contains style.css, logo.png and backgr.jpg)
   * templates
   * uploads (photos get uploaded and thumbnailed here , before sending to ECS)
* Environment variables (set them up in Cloud Foundry)
   * ECS_host (if you don't have one, you can test "object.ecstestdrive.com")
   * ECS_access_key
   * ECS_secret
   * bucket (the name of the ECS bucket)
   * object_access_URL (for details, see the note below)
* Redis instance in Cloud Foundry
* sessions.txt file contains details about each session in the conference
   * Fields are separated by ";" so that you can use commas in the event description
   * The first field is the session code and cannot contain spaces

Note: EMC's Elastic Cloud Storage (ECS) provides an S3 compatible interface. The main difference is that it uses a "namespace" which can be likened to a tenant. This enables different tenants to use the same bucket name. In order to access objects from a bucket the namespace needs to be included in the url as follows:

http://namespace.public.ecstestdrive.com/bucketname/objectname

Hence the environment variable "object_access_URL" needs to contain the "namespace.public.ecstestdrive.com" portion.

Enjoy,

Alberto
