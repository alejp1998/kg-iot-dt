FROM clearlinux/python:3

#ENV 

RUN mkdir -p /home/iotdt
RUN mkdir -p /home/social-network
RUN pip install typedb-client
RUN pip install paho-mqtt
RUN pip install numpy


COPY ./iotdt /home/iotdt
COPY ./social-network /home/social-network

#CMD ["python3", "/home/social-network/typedb_init.py"]
CMD ["python3", "/home/iotdt/test.py"]