import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsProvider extends ChangeNotifier {
  static const _kSensitivity = 'sensitivityLevel';
  static const _kFilterNudity = 'filterNudity';
  static const _kFilterViolence = 'filterViolence';
  static const _kFilterProfanity = 'filterProfanity';
  static const _kFilterLGBTQ = 'filterLGBTQ';
  static const _kBlockedThemes = 'blockedThemes';

  double _sensitivityLevel = 0.75; // BR-01 default
  bool _filterNudity = true;
  bool _filterViolence = true;
  bool _filterProfanity = true;
  bool _filterLGBTQ = false;
  List<String> _blockedThemes = const [];
  final List<String> _liveLogs = [];

  double get sensitivityLevel => _sensitivityLevel;
  bool get filterNudity => _filterNudity;
  bool get filterViolence => _filterViolence;
  bool get filterProfanity => _filterProfanity;
  bool get filterLGBTQ => _filterLGBTQ;
  List<String> get blockedThemes => List.unmodifiable(_blockedThemes);
  List<String> get liveLogs => List.unmodifiable(_liveLogs);

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    _sensitivityLevel = prefs.getDouble(_kSensitivity) ?? _sensitivityLevel;
    _filterNudity = prefs.getBool(_kFilterNudity) ?? _filterNudity;
    _filterViolence = prefs.getBool(_kFilterViolence) ?? _filterViolence;
    _filterProfanity = prefs.getBool(_kFilterProfanity) ?? _filterProfanity;
    _filterLGBTQ = prefs.getBool(_kFilterLGBTQ) ?? _filterLGBTQ;
    _blockedThemes = prefs.getStringList(_kBlockedThemes) ?? _blockedThemes;
    notifyListeners();
  }

  Future<void> _save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_kSensitivity, _sensitivityLevel);
    await prefs.setBool(_kFilterNudity, _filterNudity);
    await prefs.setBool(_kFilterViolence, _filterViolence);
    await prefs.setBool(_kFilterProfanity, _filterProfanity);
    await prefs.setBool(_kFilterLGBTQ, _filterLGBTQ);
    await prefs.setStringList(_kBlockedThemes, _blockedThemes);
  }

  Future<void> setSensitivity(double value) async {
    final clamped = value.clamp(0.0, 1.0);
    _sensitivityLevel = clamped;
    await _save();
    notifyListeners();
  }

  Future<void> toggleNudity(bool value) async {
    _filterNudity = value;
    await _save();
    notifyListeners();
  }

  Future<void> toggleViolence(bool value) async {
    _filterViolence = value;
    await _save();
    notifyListeners();
  }

  Future<void> toggleProfanity(bool value) async {
    _filterProfanity = value;
    await _save();
    notifyListeners();
  }

  Future<void> toggleLGBTQ(bool value) async {
    _filterLGBTQ = value;
    await _save();
    notifyListeners();
  }

  Future<void> setBlockedThemes(List<String> themes) async {
    _blockedThemes = themes.map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
    await _save();
    notifyListeners();
  }

  Future<void> addBlockedTheme(String theme) async {
    final v = theme.trim();
    if (v.isEmpty) return;
    _blockedThemes = [..._blockedThemes.where((e) => e.toLowerCase() != v.toLowerCase()), v];
    await _save();
    notifyListeners();
  }

  Future<void> removeBlockedTheme(String theme) async {
    final v = theme.trim().toLowerCase();
    _blockedThemes = _blockedThemes.where((e) => e.toLowerCase() != v).toList();
    await _save();
    notifyListeners();
  }

  void addLog(String message) {
    // Keep a rolling buffer, e.g., 200 entries
    _liveLogs.add(message);
    if (_liveLogs.length > 200) {
      _liveLogs.removeAt(0);
    }
    notifyListeners();
  }
}
