from tkinter import *
import tkinter.messagebox
from tkinter import messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
	RTSP_VERSION = "RTSP/1.0"
	TRANSPORT = "RTP/UDP"

	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		
	# THIS GUI IS JUST FOR REFERENCE ONLY, STUDENTS HAVE TO CREATE THEIR OWN GUI 	
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)
		
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)
		
		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 
	
	def setupMovie(self):
		"""Setup button handler.
			- send request SETUP if state is INIT
		"""
		if self.state == self.INIT: self.sendRtspRequest(self.SETUP)
	
	def exitClient(self):
		"""Teardown button handler.
			- send request TEARDOWN
			- close windows
			- remove cache
		"""
		if self.state != self.INIT:
			self.sendRtspRequest(self.TEARDOWN)
			self.master.destroy()
			os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)
		else:
			self.master.destroy()

	def pauseMovie(self):
		"""Pause button handler.
			- send request PAUSE if state is PLAYING
		"""
		if self.state == self.PLAYING: self.sendRtspRequest(self.PAUSE)
	
	def playMovie(self):
		"""Play button handler.
			- create new thread to listen RTP packets
			- get event
			- send request PLAY
		"""
		if self.state == self.READY:
			threading.Thread(target = self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)
	
	def listenRtp(self):		
		"""Listen for RTP packets."""
		while True:
			try:
				"""
					- receive packet
					- decode
					- update frame
				"""
				print("Listening ...")
				data = self.rtpSocket.recv(20480)
				if data:
					rtp_packet = RtpPacket()
					rtp_packet.decode(data)
					cur_frame = rtp_packet.seqNum()
					print("Current SeqNum: " + str(cur_frame))
					if cur_frame > self.frameNbr:
						self.frameNbr = cur_frame
						self.updateMovie(self.writeFrame(rtp_packet.getPayload()))
			except:
				"""
					- stop listen if PAUSE or TEARDOWN
					- if TEARDOWN, close RTP socket
				"""
				if self.playEvent.isSet(): break
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break
					
	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cache_name = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cache_name, "wb")
		file.write(data)
		file.close()
		return cache_name
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		img = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = img, height = 288)
		self.label.image = img
		
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			warning_1 = "Connection Failed"
			warning_2 = "Connection to '" + str(self.serverAddr) + "' failed."
			messagebox.showwarning(warning_1, warning_2)
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		# Setup
		if requestCode == self.SETUP and self.state == self.INIT:
			# make new thread to receive RTSP reply
			threading.Thread(target=self.recvRtspReply).start() 
			# Update RTSP sequence number.
			self.rtspSeq+=1
			# Write the RTSP request to be sent.
			request = "SETUP %s %s" % (self.fileName,self.RTSP_VERSION)
			request+="\nCSeq: %d" % self.rtspSeq
			request+="\nTransport: %s; client_port= %d" % (self.TRANSPORT,self.rtpPort)
			# Keep track of the sent request.
			self.requestSent = self.SETUP
		# Play
		elif requestCode == self.PLAY and self.state == self.READY:
			# Update RTSP sequence number
			self.rtspSeq += 1
			# Write RTSP request
			request = "PLAY %s %s" % (self.fileName, self.RTSP_VERSION)
			request += "\nCSqed: %d" % self.rtspSeq
			request += "\nSession: %d" % self.sessionId
			# Keep track of the sent request
			self.requestSent = self.PLAY
		# Pause
		elif requestCode == self.PAUSE and self.state == self.PLAYING:
			# Update RTSP sequence number
			self.rtspSeq += 1
			# Write RTSP request
			request = "PAUSE %s %s" % (self.fileName, self.RTSP_VERSION)
			request += "\nCSqed: %d" % self.rtspSeq
			request += "\nSession: %d" % self.sessionId
			# Keep track of the sent request
			self.requestSent = self.PAUSE
		# Teardown
		elif requestCode == self.TEARDOWN and self.state != self.INIT:
			# Update RTSP sequence number
			self.rtspSeq += 1
			# Write RTSP request
			request = "TEARDOWN %s %s" % (self.fileName, self.RTSP_VERSION)
			request += "\nCSqed: %d" % self.rtspSeq
			request += "\nSession: %d" % self.sessionId
			# Keep track of the sent request
			self.requestSent = self.TEARDOWN
		else:	return
		# Send RTSP request
		self.rtspSocket.send(request.encode())
		print("\nData Sent:\n" + request)	

	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			#Get reply
			if reply:	self.parseRtspReply(reply)
			# Teardown request, close RTSP socket
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break

	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.decode().split('\n')
		seqNum = int(lines[1].split(' ')[1])
		# Process only if the server reply's seqnum is the same as the request's
		if seqNum == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			# New RTSP session ID
			if self.sessionId == 0: self.sessionId = session
			# Process only if the session ID is the same
			if self.sessionId == session:
				# Code 200 OK
				if int(lines[0].split(' ')[1]) == 200:
					if self.requestSent == self.SETUP:
						self.state = self.READY
						self.openRtpPort()
					elif self.requestSent == self.PLAY:
						self.state = self.PLAYING
					elif self.requestSent == self.PAUSE:
						self.state = self.READY
						# A play thread exits. A new thread is created on resume
						self.playEvent.set()
					elif self.requestSent == self.TEARDOWN:
						self.state = self.INIT
						# Set flag to close socket
						self.teardownAcked = 1 	

	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket.settimeout(0.5)
		try:
			# Bind the socket to the address
			self.state = self.READY
			self.rtpSocket.bind(('', self.rtpPort))
		except:
			warning_1 = "Unable to Bind"
			warning_2 ="Unable to bind PORT = %d" % self.rtpPort
			messagebox.showwarning(warning_1, warning_2)	

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: self.playMovie()
