import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/settings_provider.dart';

class ContentFilterScreen extends StatelessWidget {
  const ContentFilterScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Content Filters'),
      ),
      body: Consumer<SettingsProvider>(
        builder: (context, settings, _) {
          return ListView(
            children: [
              SwitchListTile(
                title: const Text('Nudity'),
                subtitle: const Text('Blur or block nudity content'),
                value: settings.filterNudity,
                onChanged: (v) => settings.toggleNudity(v),
                secondary: const Icon(Icons.no_adult_content),
              ),
              SwitchListTile(
                title: const Text('Violence'),
                subtitle: const Text('Filter violent or graphic content'),
                value: settings.filterViolence,
                onChanged: (v) => settings.toggleViolence(v),
                secondary: const Icon(Icons.sports_kabaddi),
              ),
              SwitchListTile(
                title: const Text('Profanity'),
                subtitle: const Text('Mute offensive language in audio'),
                value: settings.filterProfanity,
                onChanged: (v) => settings.toggleProfanity(v),
                secondary: const Icon(Icons.volume_off),
              ),
              SwitchListTile(
                title: const Text('LGBTQ+'),
                subtitle: const Text('Filter LGBTQ+ themes (disabled by default)'),
                value: settings.filterLGBTQ,
                onChanged: (v) => settings.toggleLGBTQ(v),
                secondary: const Icon(Icons.diversity_3),
              ),
            ],
          );
        },
      ),
    );
  }
}
