import React, { useEffect, useState, useContext } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert, ActivityIndicator, Modal, TextInput, Image, Switch, ScrollView } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { API_BASE_URL } from '../../constants';
import { SettingsContext } from '../../contexts/SettingsContext';

export default function ProfileScreen() {
  const [loading, setLoading] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [profileName, setProfileName] = useState('Farmer Account');
  const [profilePic, setProfilePic] = useState<string | null>(null);
  const [editNameInput, setEditNameInput] = useState('');
  const [settingsModalVisible, setSettingsModalVisible] = useState(false);
  const [helpModalVisible, setHelpModalVisible] = useState(false);
  
  const { isDarkMode, setIsDarkMode, pushNotifications, setPushNotifications, language, setLanguage, t } = useContext(SettingsContext);
  const router = useRouter();

  useEffect(() => {
    loadProfileData();
  }, []);

  const loadProfileData = async () => {
    try {
      const storedName = await AsyncStorage.getItem('profileName');
      const storedPic = await AsyncStorage.getItem('profilePic');

      if (storedName) setProfileName(storedName);
      if (storedPic) setProfilePic(storedPic);
    } catch (err) {
      console.error("Failed to load profile data:", err);
    }
  };

  const handleSaveProfile = async () => {
    if (editNameInput.trim()) {
      setProfileName(editNameInput);
      await AsyncStorage.setItem('profileName', editNameInput);
    }
    setEditModalVisible(false);
  };

  const handlePickImage = async () => {
    Alert.alert(
      "Profile Photo",
      "Choose an option",
      [
        {
          text: "Take Photo",
          onPress: async () => {
            const { status } = await ImagePicker.requestCameraPermissionsAsync();
            if (status !== 'granted') {
              Alert.alert('Permission Denied', 'Sorry, we need camera permissions to make this work!');
              return;
            }
            const result = await ImagePicker.launchCameraAsync({
              allowsEditing: true,
              aspect: [1, 1],
              quality: 0.5,
            });
            if (!result.canceled) {
              setProfilePic(result.assets[0].uri);
              await AsyncStorage.setItem('profilePic', result.assets[0].uri);
            }
          }
        },
        {
          text: "Choose from Gallery",
          onPress: async () => {
            const result = await ImagePicker.launchImageLibraryAsync({
              mediaTypes: ['images'],
              allowsEditing: true,
              aspect: [1, 1],
              quality: 0.5,
            });
            if (!result.canceled) {
              setProfilePic(result.assets[0].uri);
              await AsyncStorage.setItem('profilePic', result.assets[0].uri);
            }
          }
        },
        { text: "Cancel", style: "cancel" }
      ]
    );
  };

  const handleLogout = async () => {
    Alert.alert(
      "Logout",
      "Are you sure you want to logout?",
      [
        { text: "Cancel", style: "cancel" },
        { 
          text: "Logout", 
          style: "destructive",
          onPress: async () => {
            try {
              await AsyncStorage.removeItem('userToken');
              router.replace('/');
            } catch (err) {
              console.error("Logout error:", err);
            }
          }
        }
      ]
    );
  };

  return (
    <View style={[styles.mainContainer, isDarkMode ? styles.darkMainContainer : null]}>
      <View style={[styles.header, isDarkMode ? styles.darkHeader : null]}>
        <Text style={[styles.headerTitle, isDarkMode ? styles.darkText : null]}>{t('Profile')}</Text>
      </View>

      <ScrollView contentContainerStyle={styles.contentContainer}>
        {/* Profile Header */}
        <View style={[styles.profileHeader, isDarkMode ? styles.darkCard : null]}>
          <TouchableOpacity style={styles.avatarContainer} onPress={handlePickImage}>
            {profilePic ? (
              <Image source={{ uri: profilePic }} style={styles.avatarImage} />
            ) : (
              <Ionicons name="person" size={60} color="#2E7D32" />
            )}
            <View style={styles.editIconBadge}>
              <Ionicons name="camera" size={14} color="#FFF" />
            </View>
          </TouchableOpacity>
          <Text style={[styles.profileName, isDarkMode ? styles.darkText : null]}>{profileName}</Text>
          <Text style={styles.profileRole}>{t('Farmer')}</Text>
        </View>

        {/* Menu Items */}
        <View style={[styles.menuContainer, isDarkMode ? styles.darkCard : null]}>
          <TouchableOpacity style={[styles.menuItem, isDarkMode ? styles.darkBorder : null]} onPress={() => {
            setEditNameInput(profileName);
            setEditModalVisible(true);
          }}>
            <View style={styles.menuItemLeft}>
              <Ionicons name="person-outline" size={24} color={isDarkMode ? "#FFF" : "#555"} />
              <Text style={[styles.menuItemText, isDarkMode ? styles.darkText : null]}>{t('Edit Name')}</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#CCC" />
          </TouchableOpacity>

          <TouchableOpacity style={[styles.menuItem, isDarkMode ? styles.darkBorder : null]} onPress={() => setSettingsModalVisible(true)}>
            <View style={styles.menuItemLeft}>
              <Ionicons name="settings-outline" size={24} color={isDarkMode ? "#FFF" : "#555"} />
              <Text style={[styles.menuItemText, isDarkMode ? styles.darkText : null]}>{t('Settings')}</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#CCC" />
          </TouchableOpacity>

          <TouchableOpacity style={[styles.menuItem, isDarkMode ? styles.darkBorder : null]} onPress={() => setHelpModalVisible(true)}>
            <View style={styles.menuItemLeft}>
              <Ionicons name="help-circle-outline" size={24} color={isDarkMode ? "#FFF" : "#555"} />
              <Text style={[styles.menuItemText, isDarkMode ? styles.darkText : null]}>{t('Help & Support')}</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#CCC" />
          </TouchableOpacity>

          <TouchableOpacity style={[styles.menuItem, { borderBottomWidth: 0 }]} onPress={handleLogout}>
            <View style={styles.menuItemLeft}>
              <Ionicons name="log-out-outline" size={24} color="#D32F2F" />
              <Text style={[styles.menuItemText, { color: '#D32F2F' }]}>{t('Logout')}</Text>
            </View>
          </TouchableOpacity>
        </View>
      </ScrollView>

      {/* Edit Profile Modal */}
      <Modal visible={editModalVisible} transparent={true} animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, isDarkMode ? styles.darkCard : null]}>
            <Text style={[styles.modalTitle, isDarkMode ? styles.darkText : null]}>{t('Edit Profile Name')}</Text>
            <TextInput
              style={[styles.input, isDarkMode ? { color: '#FFF', borderColor: '#444' } : null]}
              value={editNameInput}
              onChangeText={setEditNameInput}
              placeholder={t('Enter new name')}
              placeholderTextColor={isDarkMode ? "#888" : "#999"}
            />
            <View style={styles.modalActions}>
              <TouchableOpacity style={[styles.btn, styles.cancelBtn]} onPress={() => setEditModalVisible(false)}>
                <Text style={styles.btnTextDark}>{t('Cancel')}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.btn, styles.saveBtn]} onPress={handleSaveProfile}>
                <Text style={styles.btnTextLight}>{t('Save')}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Settings Modal */}
      <Modal visible={settingsModalVisible} transparent={true} animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, isDarkMode ? styles.darkCard : null]}>
            <Text style={[styles.modalTitle, isDarkMode ? styles.darkText : null]}>{t('Settings')}</Text>
            
            <View style={[styles.settingRow, isDarkMode ? styles.darkBorder : null]}>
              <Text style={[styles.settingText, isDarkMode ? styles.darkText : null]}>{t('Dark Mode')}</Text>
              <Switch 
                value={isDarkMode} 
                onValueChange={setIsDarkMode} 
              />
            </View>

            <View style={[styles.settingRow, isDarkMode ? styles.darkBorder : null]}>
              <Text style={[styles.settingText, isDarkMode ? styles.darkText : null]}>{t('Push Notifications')}</Text>
              <Switch 
                value={pushNotifications} 
                onValueChange={setPushNotifications} 
              />
            </View>

            <View style={[styles.settingRow, isDarkMode ? styles.darkBorder : null]}>
              <Text style={[styles.settingText, isDarkMode ? styles.darkText : null]}>{t('Language')}</Text>
              <TouchableOpacity 
                style={styles.langBtn} 
                onPress={() => {
                  const newLang = language === 'English' ? 'Hindi' : 'English';
                  setLanguage(newLang);
                }}
              >
                <Text style={styles.langBtnText}>{language}</Text>
                <Ionicons name="swap-horizontal" size={16} color="#2E7D32" style={{ marginLeft: 5 }} />
              </TouchableOpacity>
            </View>

            <TouchableOpacity style={[styles.btn, styles.cancelBtn, { marginTop: 20 }]} onPress={() => setSettingsModalVisible(false)}>
              <Text style={styles.btnTextDark}>{t('Close')}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Help Modal */}
      <Modal visible={helpModalVisible} transparent={true} animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, isDarkMode ? styles.darkCard : null]}>
            <Text style={[styles.modalTitle, isDarkMode ? styles.darkText : null]}>{t('Help & Support')}</Text>
            <Text style={[{ marginBottom: 20 }, isDarkMode ? { color: '#CCC' } : null]}>For assistance, please contact us at support@biomassengine.com.</Text>
            <TouchableOpacity style={[styles.btn, styles.cancelBtn]} onPress={() => setHelpModalVisible(false)}>
              <Text style={styles.btnTextDark}>{t('Close')}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

    </View>
  );
}

const styles = StyleSheet.create({
  mainContainer: { flex: 1, backgroundColor: '#f5f5f5' },
  header: { padding: 20, paddingTop: 50, backgroundColor: '#FFF', elevation: 3, borderBottomWidth: 1, borderBottomColor: '#E0E0E0' },
  headerTitle: { fontSize: 22, fontWeight: 'bold', color: '#2E7D32' },
  contentContainer: { padding: 20 },
  profileHeader: { alignItems: 'center', marginBottom: 30, backgroundColor: '#FFF', padding: 20, borderRadius: 15, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.2, shadowRadius: 2 },
  avatarContainer: { width: 100, height: 100, borderRadius: 50, backgroundColor: '#E8F5E9', justifyContent: 'center', alignItems: 'center', marginBottom: 15, position: 'relative' },
  avatarImage: { width: 100, height: 100, borderRadius: 50 },
  editIconBadge: { position: 'absolute', bottom: 0, right: 0, backgroundColor: '#2E7D32', width: 28, height: 28, borderRadius: 14, justifyContent: 'center', alignItems: 'center', borderWidth: 2, borderColor: '#FFF' },
  profileName: { fontSize: 20, fontWeight: 'bold', color: '#333', marginBottom: 5 },
  profileRole: { fontSize: 14, color: '#777' },
  menuContainer: { backgroundColor: '#FFF', borderRadius: 15, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.2, shadowRadius: 2, overflow: 'hidden' },
  menuItem: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 20, borderBottomWidth: 1, borderBottomColor: '#F0F0F0' },
  menuItemLeft: { flexDirection: 'row', alignItems: 'center' },
  menuItemText: { fontSize: 16, color: '#333', marginLeft: 15 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 20 },
  modalContent: { backgroundColor: '#FFF', padding: 25, borderRadius: 15 },
  modalTitle: { fontSize: 18, fontWeight: 'bold', marginBottom: 15 },
  input: { borderWidth: 1, borderColor: '#DDD', padding: 12, borderRadius: 8, fontSize: 16, marginBottom: 20 },
  modalActions: { flexDirection: 'row', justifyContent: 'space-between' },
  btn: { flex: 1, padding: 12, borderRadius: 8, alignItems: 'center', marginHorizontal: 5 },
  cancelBtn: { backgroundColor: '#E0E0E0' },
  saveBtn: { backgroundColor: '#2E7D32' },
  btnTextDark: { color: '#333', fontWeight: 'bold' },
  btnTextLight: { color: '#FFF', fontWeight: 'bold' },
  settingRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 15, borderBottomWidth: 1, borderBottomColor: '#F0F0F0' },
  settingText: { fontSize: 16, color: '#333' },
  langBtn: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#E8F5E9', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 15 },
  langBtnText: { color: '#2E7D32', fontWeight: 'bold' },
  darkMainContainer: { backgroundColor: '#121212' },
  darkHeader: { backgroundColor: '#1E1E1E', borderBottomColor: '#333' },
  darkCard: { backgroundColor: '#1E1E1E' },
  darkText: { color: '#FFF' },
  darkBorder: { borderBottomColor: '#333' }
});
