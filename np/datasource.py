#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2010-2011.

# Author(s):
 
#   Martin Raspaud <martin.raspaud@smhi.se>

# This file is part of pytroll.

# Pytroll is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.

# Pytroll is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along with
# pytroll.  If not, see <http://www.gnu.org/licenses/>.

"""A datasource for global metop granules.
"""

from posttroll.publisher import Publisher
from posttroll.message import Message
from posttroll.message_broadcaster import sendaddresstype
import socket
import time
from datetime import datetime, timedelta
import glob
import os

def get_own_ip():
    """Get the host's ip number.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(('smhi.se', 0))
    ip_ = sock.getsockname()[0]
    sock.close()
    return ip_




PATH = "/data/prod/satellit/metop"

PATTERN = "AVHR_xxx_1B_M02_*"

stamp = datetime.utcnow() - timedelta(hours=1)

def get_file_list(timestamp):
    """Get files.
    """
    flist = glob.glob(os.path.join(PATH, PATTERN))
    result = []
    for fil in flist:
        if not os.path.isfile(fil):
            continue
        mtime = os.stat(fil).st_mtime
        dt_ = datetime.utcfromtimestamp(mtime)        
        if timestamp < dt_:
            result.append((fil, dt_))

    return sorted(result, lambda x, y: cmp(x[1], y[1]))

def younger_than_stamp_files():
    """Uses glob polling to get new files.
    """

    global stamp
    for fil, tim in get_file_list(stamp):
        yield os.path.join(PATH, fil)
        stamp = tim

def send_new_files():
    """Create messages and send away.
    """
    for fil in younger_than_stamp_files():
        base = os.path.basename(fil)
        metadata = {
            "filename": base,
            "URIs": ["file://"+fil],
            "type": "HRPT 1b",
            "format": "EPS 1b",
            "time_of_first_scanline": datetime.strptime(base[16:30],
                                                        "%Y%m%d%H%M%S").isoformat(),
            "time_of_last_scanline": datetime.strptime(base[32:46],
                                                        "%Y%m%d%H%M%S").isoformat()}
        import pprint
        pprint.pprint(metadata)
        yield Message('/dc/polar/gds', 'file', metadata)



PUB_ADDRESS = "tcp://" + str(get_own_ip()) + ":9000"
BROADCASTER = sendaddresstype('p1', PUB_ADDRESS, "HRPT 1b", 2).start()

time.sleep(10)

PUB = Publisher(PUB_ADDRESS)

try:
    #for msg in SUB(timeout=1):
    #    print "Consumer got", msg
    counter = 0
    while True:
        counter += 1
        for i in send_new_files():
            print "publishing " + str(i)
            PUB.send(str(i))
        time.sleep(60)
except KeyboardInterrupt:
    print "terminating datasource..."
    BROADCASTER.stop()
    PUB.stop()
