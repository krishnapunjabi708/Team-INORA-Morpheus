import 'dart:async';
import 'package:flutter/material.dart';
import 'package:vapi/vapi.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:farmmatrix/screens/home/home_screen.dart';

class VoiceAssistantScreen extends StatefulWidget {
  const VoiceAssistantScreen({Key? key}) : super(key: key);

  @override
  State<VoiceAssistantScreen> createState() => _VoiceAssistantScreenState();
}

class _VoiceAssistantScreenState extends State<VoiceAssistantScreen> {
  bool _isLoading = true;
  bool _hasError = false;
  bool _isCallActive = false;
  String _callStatus = 'Initializing...';
  late Vapi _vapi;
  StreamSubscription? _eventSubscription;

  // Vapi credentials
  static const String _publicKey = '99983d92-888f-4951-b2a8-575c364857b5';
  static const String _assistantId = '3bd841e5-7b32-4da1-9e4e-ca57e9829b51';

  @override
  void initState() {
    super.initState();
    _initializeVapi();
    _requestPermissions();
  }

  @override
  void dispose() {
    _eventSubscription?.cancel();
    _vapi.stop();
    super.dispose();
  }

  void _initializeVapi() {
    try {
      _vapi = Vapi(_publicKey);
      _eventSubscription = _vapi.onEvent.listen((event) {
        print('Vapi event: ${event.label}');
        setState(() {
          switch (event.label) {
            case 'call-start':
              _isCallActive = true;
              _callStatus = 'Connected - Assistant Speaking';
              break;
            case 'call-end':
              _isCallActive = false;
              _callStatus = 'Call ended - Returning home...';
              Future.delayed(const Duration(seconds: 2), () {
                Navigator.pop(context);
              });
              break;
            case 'speech-start':
              _callStatus = 'Listening to you...';
              break;
            case 'speech-end':
              _callStatus = 'Processing your request...';
              break;
            case 'message':
              if (event.value is Map && event.value['role'] == 'assistant') {
                _callStatus = 'Assistant Speaking';
              }
              print('Message: ${event.value}');
              break;
            case 'error':
              _hasError = true;
              _callStatus =
                  'Error: ${event.value['message'] ?? 'Unknown error'}';
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(
                    'Vapi Error: ${event.value['message'] ?? 'Unknown error'}',
                  ),
                  backgroundColor: Colors.red,
                ),
              );
              break;
          }
        });
      });
    } catch (e) {
      print('Error initializing Vapi: $e');
      setState(() {
        _hasError = true;
        _callStatus = 'Error initializing Vapi: $e';
      });
    }
  }

  Future<void> _requestPermissions() async {
    try {
      var status = await Permission.microphone.status;
      print('Microphone permission status: $status');
      if (!status.isGranted) {
        status = await Permission.microphone.request();
        print('Microphone permission request result: $status');
        if (!status.isGranted) {
          setState(() {
            _hasError = true;
            _callStatus = 'Microphone permission denied';
          });
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Microphone permission is required.'),
              backgroundColor: Colors.red,
            ),
          );
          return;
        }
      }
      setState(() {
        _isLoading = false;
      });
      await _startCall();
    } catch (e) {
      print('Error requesting permissions: $e');
      setState(() {
        _hasError = true;
        _callStatus = 'Error requesting permissions: $e';
      });
    }
  }

  Future<void> _startCall() async {
    setState(() {
      _callStatus = 'Connecting...';
      _isLoading = true;
    });

    try {
      await _vapi.start(assistantId: _assistantId);
      setState(() {
        _isLoading = false;
      });
    } catch (e) {
      print('Error starting call: $e');
      setState(() {
        _hasError = true;
        _callStatus = 'Error starting call: $e';
        _isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to start call: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _stopCall() async {
    try {
      await _vapi.stop();
      setState(() {
        _isCallActive = false;
        _callStatus = 'Call ended - Returning home...';
      });
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => const HomeScreen()),
      );
    } catch (e) {
      print('Error stopping call: $e');
      setState(() {
        _hasError = true;
        _callStatus = 'Error stopping call: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text("FarmMatrix Assistant"),
        backgroundColor: const Color(0xFF1B413C),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () async {
            try {
              await _stopCall(); // Stop the call first
              // Then navigate to HomeScreen
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (context) => const HomeScreen()),
              );
            } catch (e) {
              print('Error stopping call or navigating: $e');
              // Optional: Show error to user
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Could not exit properly: $e')),
              );
            }
          },
        ),
        automaticallyImplyLeading: false,
      ),

      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Icon(
                  _isCallActive ? Icons.mic : Icons.mic_off,
                  color: _isCallActive ? Colors.green : Colors.grey,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _callStatus,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.w400,
                    ),
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: Stack(
              children: [
                Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Image.asset(
                        'assets/images/voice1.png',
                        width: 120,
                        height: 120,
                        fit: BoxFit.contain,
                      ),
                      const SizedBox(height: 20),
                      Text(
                        _callStatus,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 24,
                          fontWeight: FontWeight.w300,
                        ),
                      ),
                      const SizedBox(height: 20),
                      if (_isCallActive)
                        ElevatedButton(
                          onPressed: _stopCall,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.red,
                          ),
                          child: const Text('Stop Call'),
                        ),
                    ],
                  ),
                ),
                if (_isLoading)
                  const Center(
                    child: CircularProgressIndicator(color: Colors.white),
                  ),
                if (_hasError)
                  Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(
                          Icons.error_outline,
                          size: 64,
                          color: Colors.red,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Error: $_callStatus',
                          style: const TextStyle(color: Colors.white),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: () {
                            setState(() {
                              _hasError = false;
                              _isLoading = true;
                            });
                            _startCall();
                          },
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
