This repository was originally made by Damianonymous:
https://github.com/Damianonymous/streamlink-plugins
I added a few recorders for Chaturbate (Recorder_CB), MyFreeCams (Recorder_MFC), BongaCams (Recorder_BC), Camsoda (Recorder_CS) and Cam4 (Recorder_C4).
But, with just a little bit of work, many other sites can be added.

They are based on the Showup.bat recorder made by Damianonymous:
https://github.com/Damianonymous/streamlink-plugins/tree/master/Recorder

But with some improvements:
- the files/folders used by the recorders are searched and used in the folder where Recorder-*.cmd is started.
This way it is now truly portable.
- the title of the command/cmd window shows the status of the recorder:
Select model
Name of the model (when is waiting between Streamlink attempts).
Name of the model written in uppercase - when it tries to connect and when is succeeding.
- the time interval between attempts is no longer a fixed value, it is randomly chosen between 45 and 75 seconds.
- if something was recorded during an attempt the next attempt will be started in 22..37 seconds.

Usage:

Download Recorder_*.cmd and *_Model.txt (same string for * on both).
Download Streamlink_portable.zip and Streamlink_portable.z01 into the same folder.
Then decompress Streamlink_portable.zip into the same folder where you downloaded/copied Recorder_*.cmd.
Populate the *_Model.txt text file with the models names (only lowercase)..
Start Recorder_*.cmd, chose model by index and hit Enter/Return. And repeat.

Useful information: the time interval between attempts was calculated for an average PC/Laptop, for an average internet connection and for 5..10 sessions.
For other characteristics you may need to increase it.

Have fun :)

TODO:
1. Set and use models' preferred hours. (wait time between attempts will be lower during and higher outside);
2. Combine all in one cmd batch and one models list;
3. Better handling errors;
4. Automatic start and stop for a model;
5. When model is in private enter in spy mode.
6. When it starts recording to notify the user by audio and/or by bringing the cmd window in front and so on.

