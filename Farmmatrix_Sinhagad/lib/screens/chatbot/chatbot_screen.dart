import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:farmmatrix/config/app_config.dart';
import 'package:farmmatrix/services/user_service.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:farmmatrix/screens/home/home_screen.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';

class ChatbotScreen extends StatefulWidget {
  final String? chatId;

  const ChatbotScreen({super.key, this.chatId});

  @override
  State<ChatbotScreen> createState() => _ChatbotScreenState();
}

class _ChatbotScreenState extends State<ChatbotScreen> {
  final TextEditingController _messageController = TextEditingController();
  final TextEditingController _renameController = TextEditingController();
  List<ChatMessage> _messages = [];
  bool _isTextFieldFocused = false;
  bool _isLoadingResponse = false;
  final UserService _userService = UserService();
  bool _isDrawerOpen = false;
  List<ChatHistory> _chatHistory = [];
  String _currentChatId = '';
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  late AppLocalizations loc;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    loc = AppLocalizations.of(context)!;
  }

  @override
  void initState() {
    super.initState();
    _currentChatId = widget.chatId ?? DateTime.now().millisecondsSinceEpoch.toString();
    _loadChatHistory();
    _loadMessages();
  }

  Future<void> _loadChatHistory() async {
    final prefs = await SharedPreferences.getInstance();
    final historyJson = prefs.getStringList('chat_history') ?? [];
    setState(() {
      _chatHistory = historyJson
          .map((json) => ChatHistory.fromJson(jsonDecode(json)))
          .toList();
    });
  }

  Future<void> _loadMessages() async {
    if (widget.chatId == null) return;

    final prefs = await SharedPreferences.getInstance();
    final messagesJson = prefs.getStringList('chat_${widget.chatId}') ?? [];
    setState(() {
      _messages = messagesJson
          .map((json) => ChatMessage.fromJson(jsonDecode(json)))
          .toList()
          .reversed
          .toList();
    });
  }

  Future<void> _saveMessages() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(
      'chat_$_currentChatId',
      _messages.map((msg) => jsonEncode(msg.toJson())).toList(),
    );

    final historyEntry = ChatHistory(
      id: _currentChatId,
      title: _messages.isNotEmpty
          ? _messages.last.text
          : loc.newChat,
      lastMessageTime: DateTime.now(),
    );

    final existingIndex = _chatHistory.indexWhere((chat) => chat.id == _currentChatId);
    if (existingIndex >= 0) {
      _chatHistory[existingIndex] = historyEntry;
    } else {
      _chatHistory.insert(0, historyEntry);
    }

    await prefs.setStringList(
      'chat_history',
      _chatHistory.map((chat) => jsonEncode(chat.toJson())).toList(),
    );
  }

  Future<void> _deleteChat(String chatId) async {
    final prefs = await SharedPreferences.getInstance();

    await prefs.remove('chat_$chatId');

    setState(() {
      _chatHistory.removeWhere((chat) => chat.id == chatId);
    });

    await prefs.setStringList(
      'chat_history',
      _chatHistory.map((chat) => jsonEncode(chat.toJson())).toList(),
    );

    if (chatId == _currentChatId && mounted) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => const ChatbotScreen()),
      );
    }
  }

  Future<void> _renameChat(String chatId, String newName) async {
    final prefs = await SharedPreferences.getInstance();

    final chatIndex = _chatHistory.indexWhere((chat) => chat.id == chatId);
    if (chatIndex >= 0) {
      setState(() {
        _chatHistory[chatIndex] = ChatHistory(
          id: chatId,
          title: newName,
          lastMessageTime: _chatHistory[chatIndex].lastMessageTime,
        );
      });

      await prefs.setStringList(
        'chat_history',
        _chatHistory.map((chat) => jsonEncode(chat.toJson())).toList(),
      );
    }
  }

  void _showChatOptions(ChatHistory chat) {
    showModalBottomSheet(
      context: context,
      builder: (BuildContext context) {
        return Container(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: const Icon(Icons.edit),
                title: Text(loc.rename),
                onTap: () {
                  Navigator.pop(context);
                  _showRenameDialog(chat);
                },
              ),
              ListTile(
                leading: const Icon(Icons.delete, color: Colors.red),
                title: Text(
                  loc.delete,
                  style: const TextStyle(color: Colors.red),
                ),
                onTap: () {
                  Navigator.pop(context);
                  _showDeleteConfirmation(chat);
                },
              ),
            ],
          ),
        );
      },
    );
  }

  void _showRenameDialog(ChatHistory chat) {
    _renameController.text = chat.title;
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(loc.renameChat),
          content: TextField(
            controller: _renameController,
            decoration: InputDecoration(
              hintText: loc.enterNewChatName,
              border: const OutlineInputBorder(),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text(loc.cancel),
            ),
            TextButton(
              onPressed: () {
                final newName = _renameController.text.trim();
                if (newName.isNotEmpty) {
                  _renameChat(chat.id, newName);
                }
                Navigator.pop(context);
              },
              child: Text(loc.rename),
            ),
          ],
        );
      },
    );
  }

  void _showDeleteConfirmation(ChatHistory chat) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(loc.deleteChat),
          content: Text(loc.deleteChatConfirmation),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text(loc.cancel),
            ),
            TextButton(
              onPressed: () {
                Navigator.pop(context);
                _deleteChat(chat.id);
              },
              style: TextButton.styleFrom(foregroundColor: Colors.red),
              child: Text(loc.delete),
            ),
          ],
        );
      },
    );
  }

  @override
  void dispose() {
    _messageController.dispose();
    _renameController.dispose();
    _saveMessages();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    loc = AppLocalizations.of(context)!;

    return Scaffold(
      key: _scaffoldKey,
      appBar: AppBar(
        title: Text(loc.farmMatrixAssistant),
        backgroundColor: const Color(0xFF178D38),
        foregroundColor: Colors.white,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (context) => const HomeScreen()),
            );
          },
        ),
      ),
      body: Column(
        children: [
          // Drawer toggle button (hamburger menu)
          Container(
            width: double.infinity,
            color: Colors.grey[100],
            child: IconButton(
              icon: const Icon(Icons.menu),
              alignment: Alignment.centerLeft,
              onPressed: () => _scaffoldKey.currentState?.openDrawer(),
            ),
          ),
          Expanded(
            child: Stack(
              children: [
                Column(
                  children: [
                    Expanded(
                      child: Container(
                        padding: const EdgeInsets.all(16),
                        color: Colors.grey[100],
                        child: _messages.isEmpty
                            ? Center(
                                child: Text(
                                  loc.askYourAssistant,
                                  style: const TextStyle(
                                    fontSize: 18,
                                    color: Colors.grey,
                                  ),
                                ),
                              )
                            : ListView.builder(
                                reverse: true,
                                itemCount: _messages.length,
                                itemBuilder: (context, index) {
                                  return _messages[index];
                                },
                              ),
                      ),
                    ),
                    _buildInputUI(),
                  ],
                ),
                if (_isLoadingResponse)
                  const Center(child: CircularProgressIndicator()),
              ],
            ),
          ),
        ],
      ),
      drawer: _buildDrawer(),
    );
  }

  Widget _buildDrawer() {
    return Drawer(
      child: Column(
        children: [
          Container(
            height: 100,
            color: const Color(0xFF178D38),
            padding: const EdgeInsets.only(top: 40, left: 16),
            alignment: Alignment.centerLeft,
            child: Text(
              loc.chatHistory,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.add),
            title: Text(loc.newChat),
            onTap: () {
              Navigator.pop(context);
              Navigator.pushReplacement(
                context,
                MaterialPageRoute(builder: (context) => const ChatbotScreen()),
              );
            },
          ),
          const Divider(),
          Expanded(
            child: ListView.builder(
              itemCount: _chatHistory.length,
              itemBuilder: (context, index) {
                final chat = _chatHistory[index];
                return ListTile(
                  title: Text(
                    chat.title.length > 30
                        ? '${chat.title.substring(0, 30)}...'
                        : chat.title,
                  ),
                  onTap: () {
                    Navigator.pop(context);
                    Navigator.pushReplacement(
                      context,
                      MaterialPageRoute(
                        builder: (context) => ChatbotScreen(chatId: chat.id),
                      ),
                    );
                  },
                  onLongPress: () => _showChatOptions(chat),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputUI() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: Colors.white,
      child: Row(
        children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: const Color(0xFFF1F1F1),
                borderRadius: BorderRadius.circular(20),
              ),
              child: TextField(
                controller: _messageController,
                onChanged: (text) => setState(() {}),
                decoration: InputDecoration(
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 12,
                  ),
                  hintText: loc.askAnything,
                  hintStyle: const TextStyle(color: Colors.grey),
                  border: InputBorder.none,
                ),
                onSubmitted: (text) {
                  if (text.trim().isNotEmpty) _sendTextMessage();
                },
              ),
            ),
          ),
          if (_messageController.text.trim().isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(left: 8.0),
              child: IconButton(
                icon: const Icon(
                  Icons.send,
                  color: Color(0xFF178D38),
                  size: 28,
                ),
                onPressed: _sendTextMessage,
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _sendTextMessage() async {
    final message = _messageController.text.trim();
    if (message.isEmpty) return;

    _messageController.clear();
    setState(() {
      _messages.insert(0, ChatMessage(text: message, isUser: true));
      _messages.insert(
        0,
        ChatMessage(text: '', isUser: false, isLoading: true),
      );
      _isLoadingResponse = true;
    });

    await _processMessage(message);
    await _saveMessages();
  }

  Future<void> _processMessage(String message) async {
    try {
      final user = await _userService.getCurrentUserData();
      final userName = user?.fullName ?? loc.defaultUser;

      final requestBody = {"question": message, "username": userName};

      final response = await http.post(
        Uri.parse('https://rituja04-farmmatrix-chatbot-api.hf.space/generate'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(requestBody),
      );

      if (response.statusCode == 200) {
        final responseData = jsonDecode(utf8.decode(response.bodyBytes));
        final botResponse = responseData['answer'] ?? loc.apiErrorMessage;

        setState(() {
          _messages.removeAt(0);
          _messages.insert(0, ChatMessage(text: botResponse, isUser: false));
        });
      } else {
        throw Exception('API Error: ${response.statusCode}');
      }
    } catch (e) {
      setState(() {
        _messages.removeAt(0);
        _messages.insert(
          0,
          ChatMessage(text: loc.apiErrorMessage, isUser: false),
        );
      });
    } finally {
      setState(() => _isLoadingResponse = false);
    }
  }
}

// ────────────────────────────────────────────────
// ChatHistory & ChatMessage classes remain unchanged
// ────────────────────────────────────────────────

class ChatHistory {
  final String id;
  final String title;
  final DateTime lastMessageTime;

  ChatHistory({
    required this.id,
    required this.title,
    required this.lastMessageTime,
  });

  factory ChatHistory.fromJson(Map<String, dynamic> json) {
    return ChatHistory(
      id: json['id'],
      title: json['title'],
      lastMessageTime: DateTime.parse(json['lastMessageTime']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'lastMessageTime': lastMessageTime.toIso8601String(),
    };
  }
}

class ChatMessage extends StatelessWidget {
  final String text;
  final bool isUser;
  final bool isLoading;

  const ChatMessage({
    super.key,
    required this.text,
    required this.isUser,
    this.isLoading = false,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      text: json['text'],
      isUser: json['isUser'],
      isLoading: json['isLoading'] ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {'text': text, 'isUser': isUser, 'isLoading': isLoading};
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isUser && !isLoading) _buildBotAvatar(),
          if (isLoading) _buildBotAvatar(),
          _buildMessageBubble(context),
          if (isUser) _buildUserAvatar(),
        ],
      ),
    );
  }

  Widget _buildBotAvatar() {
    return Container(
      margin: const EdgeInsets.only(right: 8),
      child: CircleAvatar(
        backgroundColor: Colors.grey[300],
        child: Image.asset('assets/images/logo.png', width: 24, height: 24),
      ),
    );
  }

  Widget _buildUserAvatar() {
    return Container(
      margin: const EdgeInsets.only(left: 8),
      child: const CircleAvatar(
        backgroundColor: Color(0xFFF1F1F1),
        child: Icon(Icons.person, color: Color(0xFF178D38)),
      ),
    );
  }

  Widget _buildMessageBubble(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.7,
      ),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isUser ? const Color(0xFF178D38) : Colors.grey[200],
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(12),
          topRight: const Radius.circular(12),
          bottomLeft: Radius.circular(isUser ? 12 : 0),
          bottomRight: Radius.circular(isUser ? 0 : 12),
        ),
      ),
      child: isLoading ? _buildLoadingIndicator() : Text(
        text,
        style: TextStyle(
          color: isUser ? Colors.white : Colors.black,
          fontSize: 16,
        ),
      ),
    );
  }

  Widget _buildLoadingIndicator() {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(
        3,
        (index) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 2),
          child: AnimatedContainer(
            duration: Duration(milliseconds: 500 + (index * 200)),
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: const Color(0xFF178D38),
              borderRadius: BorderRadius.circular(4),
            ),
          ),
        ),
      ),
    );
  }
}