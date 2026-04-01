import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/settings_provider.dart';

class SensitivityScreen extends StatelessWidget {
  const SensitivityScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sensitivity'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Consumer<SettingsProvider>(
          builder: (context, settings, _) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Detection Sensitivity',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Adjust how strict SafeView should be when flagging content. '
                  'Higher values mean stricter filtering.',
                  style: theme.textTheme.bodyMedium,
                ),
                const SizedBox(height: 16),
                Slider(
                  value: settings.sensitivityLevel,
                  min: 0.0,
                  max: 1.0,
                  divisions: 20,
                  label: settings.sensitivityLevel.toStringAsFixed(2),
                  onChanged: (v) => settings.setSensitivity(v),
                ),
                Align(
                  alignment: Alignment.centerRight,
                  child: Chip(
                    label: Text(
                      (settings.sensitivityLevel * 100).toStringAsFixed(0) + '%',
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(20),
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}
