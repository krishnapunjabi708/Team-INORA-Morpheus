import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:farmmatrix/config/app_config.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';

class GovernmentSchemesScreen extends StatelessWidget {
  const GovernmentSchemesScreen({super.key});

  final List<Map<String, String>> schemes = const [
    {
      'name': 'pradhanMantriFasalBimaYojana',
      'url': 'https://www.google.com/search?q=Pradhan+Mantri+Fasal+Bima+Yojana',
    },
    {
      'name': 'kisanCreditCardScheme',
      'url': 'https://www.google.com/search?q=Kisan+Credit+Card+Scheme',
    },
    {
      'name': 'paramparagatKrishiVikasYojana',
      'url': 'https://www.google.com/search?q=Paramparagat+Krishi+Vikas+Yojana',
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          AppLocalizations.of(context)!.governmentSchemes,
          style: TextStyle(
            fontFamily: AppConfig.fontFamily,
            color: Colors.white,
          ),
        ),
        backgroundColor: const Color(0xFF178D38),
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: ListView.builder(
        itemCount: schemes.length,
        itemBuilder: (context, index) {
          final scheme = schemes[index];
          return GestureDetector(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => WebViewScreen(url: scheme['url']!),
                ),
              );
            },
            child: Card(
              margin: const EdgeInsets.all(8),
              child: ListTile(
                title: Text(
                  AppLocalizations.of(context)!.getString(scheme['name']!),
                  style: TextStyle(
                    fontFamily: AppConfig.fontFamily,
                    fontSize: 16,
                  ),
                ),
                trailing: const Icon(Icons.arrow_forward),
              ),
            ),
          );
        },
      ),
    );
  }
}

class WebViewScreen extends StatefulWidget {
  final String url;

  const WebViewScreen({super.key, required this.url});

  @override
  _WebViewScreenState createState() => _WebViewScreenState();
}

class _WebViewScreenState extends State<WebViewScreen> {
  late WebViewController _controller;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..loadRequest(Uri.parse(widget.url));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          AppLocalizations.of(context)!.governmentSchemes,
          style: TextStyle(
            fontFamily: AppConfig.fontFamily,
            color: Colors.white,
          ),
        ),
        backgroundColor: const Color(0xFF178D38),
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: WebViewWidget(
        controller: _controller,
      ),
    );
  }
}

extension AppLocalizationsExtension on AppLocalizations {
  String getString(String key) {
    switch (key) {
      case 'pradhanMantriFasalBimaYojana':
        return pradhanMantriFasalBimaYojana;
      case 'kisanCreditCardScheme':
        return kisanCreditCardScheme;
      case 'paramparagatKrishiVikasYojana':
        return paramparagatKrishiVikasYojana;
      default:
        return key; // Fallback to key if not found
    }
  }
}