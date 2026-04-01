import 'package:flutter/material.dart';
import '../services/native_bridge.dart';
import 'package:provider/provider.dart';
import '../providers/settings_provider.dart';
import 'dart:async';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  StreamSubscription<dynamic>? _statusSub;

  @override
  void initState() {
    super.initState();
    _statusSub = NativeBridge.statusStream().listen((event) {
      final msg = event?.toString();
      if (msg == null || msg.isEmpty) return;
      if (!mounted) return;
      context.read<SettingsProvider>().addLog(msg);
    });
  }

  @override
  void dispose() {
    _statusSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('SafeView Dashboard'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Card(
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              color: theme.colorScheme.primaryContainer,
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Real-time Protection',
                      style: theme.textTheme.titleMedium?.copyWith(
                        color: theme.colorScheme.onPrimaryContainer,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(Icons.shield, color: theme.colorScheme.primary),
                        const SizedBox(width: 8),
                        Text(
                          'Active',
                          style: theme.textTheme.headlineSmall?.copyWith(
                            color: theme.colorScheme.onPrimaryContainer,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Your content is being analyzed for safety in real time.',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onPrimaryContainer,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: () async {
                // Check overlay permission; request if missing.
                bool granted = await NativeBridge.checkOverlayPermission();
                if (!granted) {
                  granted = await NativeBridge.requestOverlayPermission();
                }
                if (granted) {
                  final settings = context.read<SettingsProvider>();
                  final payload = {
                    'sensitivity': settings.sensitivityLevel,
                    'filter_nudity': settings.filterNudity,
                    'filter_violence': settings.filterViolence,
                    'filter_profanity': settings.filterProfanity,
                    'blocked_themes': settings.blockedThemes,
                  };
                  await NativeBridge.startProtection(payload);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Protection started')),
                    );
                  }
                } else {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Overlay permission required')),
                    );
                  }
                }
              },
              icon: const Icon(Icons.play_circle_fill),
              label: const Text('Start Protection'),
              style: ElevatedButton.styleFrom(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
            const SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: () {
                Navigator.of(context).pushNamed('/filters');
              },
              icon: const Icon(Icons.tune),
              label: const Text('Content Filters'),
              style: ElevatedButton.styleFrom(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: () {
                Navigator.of(context).pushNamed('/sensitivity');
              },
              icon: const Icon(Icons.sensors),
              label: const Text('Sensitivity'),
              style: OutlinedButton.styleFrom(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
            const SizedBox(height: 14),
            Text(
              'Live Analysis Feed',
              style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: Consumer<SettingsProvider>(
                builder: (context, settings, _) {
                  final logs = settings.liveLogs;
                  if (logs.isEmpty) {
                    return const Card(
                      child: Center(
                        child: Text('No live logs yet. Start protection to stream analysis events.'),
                      ),
                    );
                  }
                  return Card(
                    child: ListView.builder(
                      padding: const EdgeInsets.all(8),
                      reverse: true,
                      itemCount: logs.length,
                      itemBuilder: (_, i) {
                        final msg = logs[logs.length - 1 - i];
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
                          child: Text(msg, style: theme.textTheme.bodySmall),
                        );
                      },
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
