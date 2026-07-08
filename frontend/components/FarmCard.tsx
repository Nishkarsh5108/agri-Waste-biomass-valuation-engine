import React, { useState, useEffect, useRef, useContext } from 'react';
import { View, Text, StyleSheet, Image, TouchableOpacity, Modal, ActivityIndicator, Alert, TextInput, Animated } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE_URL } from '../constants';
import { SettingsContext } from '../contexts/SettingsContext';

export default function FarmCard({ data, onRefreshDashboard }: any) {
  const { isDarkMode, t } = useContext(SettingsContext);
  const [modalVisible, setModalVisible] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [locationName, setLocationName] = useState('Fetching location...');

  const scaleAnim = useRef(new Animated.Value(1)).current;

  const handlePressIn = () => {
    Animated.spring(scaleAnim, {
      toValue: 0.96,
      useNativeDriver: true,
    }).start();
  };

  const handlePressOut = () => {
    Animated.spring(scaleAnim, {
      toValue: 1,
      friction: 4,
      tension: 40,
      useNativeDriver: true,
    }).start();
  };

  // Edit State
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editName, setEditName] = useState(data?.name || '');
  const [editArea, setEditArea] = useState(data?.area_hectares?.toString() || '');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      if (data?.geojson_polygon?.coordinates) {
        try {
          // GeoJSON structure for Polygon: coordinates[0] is outer ring, [0][0] is the first point [longitude, latitude]
          const coords = data.geojson_polygon.coordinates[0][0];
          if (coords && coords.length === 2) {
            const [lon, lat] = coords;
            const locationResult = await Location.reverseGeocodeAsync({ latitude: lat, longitude: lon });
            if (locationResult && locationResult.length > 0 && isMounted) {
              const loc = locationResult[0];
              setLocationName(`${loc.city || loc.subregion || loc.district || 'Unknown'}, ${loc.region || loc.country || 'Location'}`);
            } else if (isMounted) {
              setLocationName('Location unknown');
            }
          }
        } catch (error) {
          console.log("Geocoding error", error);
          if (isMounted) setLocationName('Location unavailable');
        }
      } else {
        if (isMounted) setLocationName('No coordinates');
      }
    })();
    return () => { isMounted = false; };
  }, [data]);

  const pickImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission Denied', 'Sorry, we need camera roll permissions to make this work!');
      return;
    }

    let result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      quality: 1,
    });

    if (!result.canceled) {
      handleUpload(result.assets[0]);
    }
  };

  const takePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission Denied', 'Sorry, we need camera permissions to make this work!');
      return;
    }

    let result = await ImagePicker.launchCameraAsync({
      allowsEditing: true,
      quality: 1,
    });

    if (!result.canceled) {
      handleUpload(result.assets[0]);
    }
  };

  const handleUpload = async (image: any) => {
    setUploading(true);
    setModalVisible(false); // Close modal while uploading
    try {
      const userToken = await AsyncStorage.getItem('userToken');
      
      const formData = new FormData();
      formData.append('farm_id', data.id.toString());
      
      const uriParts = image.uri.split('/');
      const fileName = uriParts[uriParts.length - 1];
      const fileType = image.type === 'image' ? 'image/jpeg' : image.type;

      formData.append('photo', {
        uri: image.uri,
        name: fileName,
        type: fileType || 'image/jpeg',
      } as any);

      const response = await fetch(`${API_BASE_URL}/listings/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${userToken}`,
        },
        body: formData,
      });

      const resData = await response.json();

      if (response.ok || response.status === 201) {
        Alert.alert("Success", "Photo uploaded successfully! Pull down to refresh your dashboard.");
        if(onRefreshDashboard) onRefreshDashboard();
      } else {
        Alert.alert("Failed", resData.detail || "Could not upload photo.");
      }
    } catch (err) {
      console.error("Upload Error:", err);
      Alert.alert("Error", "Failed to connect to the server.");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = () => {
    Alert.alert(
      "Delete Farm",
      "Are you sure you want to delete this farm? This will also permanently remove all pickup requests associated with it.",
      [
        { text: "Cancel", style: "cancel" },
        { 
          text: "Delete", 
          style: "destructive",
          onPress: async () => {
            try {
              const userToken = await AsyncStorage.getItem('userToken');
              const res = await fetch(`${API_BASE_URL}/farms/${data.id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${userToken}` },
              });
              
              if (res.ok) {
                if(onRefreshDashboard) onRefreshDashboard();
              } else {
                Alert.alert("Error", "Failed to delete farm.");
              }
            } catch (e) {
              Alert.alert("Error", "Network error occurred.");
            }
          }
        }
      ]
    );
  };

  const handleEditSave = async () => {
    if (!editName.trim() || !editArea.trim()) {
      Alert.alert("Validation", "Please fill in all fields.");
      return;
    }
    
    setIsSaving(true);
    try {
      const userToken = await AsyncStorage.getItem('userToken');
      const res = await fetch(`${API_BASE_URL}/farms/${data.id}`, {
        method: 'PUT',
        headers: { 
          'Authorization': `Bearer ${userToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: editName,
          area_hectares: parseFloat(editArea)
        })
      });
      
      if (res.ok) {
        setEditModalVisible(false);
        if(onRefreshDashboard) onRefreshDashboard();
      } else {
        const errorData = await res.json();
        Alert.alert("Error", errorData.detail || "Failed to update farm.");
      }
    } catch (e) {
      Alert.alert("Error", "Network error occurred.");
    } finally {
      setIsSaving(false);
    }
  };

  const displayLocation = ['Fetching location...', 'Location unknown', 'Location unavailable', 'No coordinates'].includes(locationName) ? t(locationName as any) : locationName;

  return (
    <Animated.View style={[styles.card, isDarkMode ? styles.darkCard : null, { transform: [{ scale: scaleAnim }] }]}>
      <TouchableOpacity 
        onPress={() => setModalVisible(true)} 
        activeOpacity={0.8}
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
      >
        {data?.photo_s3_url ? (
          <Image 
            source={{ uri: data.photo_s3_url }} 
            style={styles.image} 
          />
        ) : (
          <View style={[styles.imagePlaceholder, isDarkMode ? { backgroundColor: '#333' } : null]}>
            <Ionicons name="image-outline" size={40} color={isDarkMode ? "#666" : "#ccc"} />
            <Text style={[styles.imageText, isDarkMode ? { color: '#AAA' } : null]}>{t('No Image Added. Tap to Add.')}</Text>
          </View>
        )}
      </TouchableOpacity>

      {uploading && (
        <View style={styles.uploadingOverlay}>
          <ActivityIndicator size="large" color="#2E7D32" />
          <Text style={styles.uploadingText}>{t('Uploading...')}</Text>
        </View>
      )}

      <View style={styles.detailsContainer}>
        <View style={styles.titleRow}>
          <Text style={[styles.title, isDarkMode ? styles.darkText : null]} numberOfLines={1}>{data?.name || t('Unnamed Farm')}</Text>
          
          <View style={styles.actionIconRow}>
            <TouchableOpacity onPress={() => setEditModalVisible(true)} style={[styles.iconButton, isDarkMode ? { backgroundColor: '#1b5e20' } : null]}>
              <Ionicons name="pencil" size={18} color={isDarkMode ? "#FFF" : "#2E7D32"} />
            </TouchableOpacity>
            <TouchableOpacity onPress={handleDelete} style={[styles.iconButton, { backgroundColor: isDarkMode ? '#b71c1c' : '#FFEBEE', marginLeft: 8 }]}>
              <Ionicons name="trash" size={18} color={isDarkMode ? "#FFF" : "#D32F2F"} />
            </TouchableOpacity>
          </View>
        </View>
        
        <View style={styles.infoRow}>
          <Ionicons name="map-outline" size={16} color={isDarkMode ? "#AAA" : "#666"} />
          <Text style={[styles.infoText, isDarkMode ? { color: '#CCC' } : null]}>{t('Area: ')}<Text style={[styles.boldText, isDarkMode ? styles.darkText : null]}>{data?.area_hectares || '0'}</Text> {t('Hectares')}</Text>
        </View>
        <View style={styles.infoRow}>
          <Ionicons name="location-outline" size={16} color="#D84315" />
          <Text style={[styles.infoText, isDarkMode ? { color: '#CCC' } : null]}>{displayLocation}</Text>
        </View>
      </View>

      {/* Image Upload Modal */}
      <Modal
        animationType="slide"
        transparent={true}
        visible={modalVisible}
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modalContainer}>
          <View style={[styles.modalContent, isDarkMode ? styles.darkCard : null]}>
            
            <TouchableOpacity style={styles.closeButton} onPress={() => setModalVisible(false)}>
              <Ionicons name="close" size={28} color={isDarkMode ? "#FFF" : "#333"} />
            </TouchableOpacity>

            <Text style={[styles.modalTitle, isDarkMode ? styles.darkText : null]}>{data?.photo_s3_url ? t("Farm Photo") : t("Add Farm Photo")}</Text>

            {data?.photo_s3_url ? (
              <Image 
                source={{ uri: data.photo_s3_url }} 
                style={styles.fullImage} 
                resizeMode="contain"
              />
            ) : (
              <View style={[styles.imagePlaceholder, isDarkMode ? { backgroundColor: '#333' } : { width: '100%', height: 250, borderRadius: 10 }]}>
                <Ionicons name="image-outline" size={60} color={isDarkMode ? "#666" : "#ccc"} />
                <Text style={[styles.imageText, isDarkMode ? { color: '#AAA' } : null]}>{t('No image available')}</Text>
              </View>
            )}

            <View style={styles.actionButtons}>
              <TouchableOpacity style={styles.actionBtn} onPress={takePhoto}>
                <Ionicons name="camera" size={24} color="#FFF" />
                <Text style={styles.actionBtnText}>{t('Take Photo')}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.actionBtn, { backgroundColor: '#4CAF50' }]} onPress={pickImage}>
                <Ionicons name="images" size={24} color="#FFF" />
                <Text style={styles.actionBtnText}>{t('Gallery')}</Text>
              </TouchableOpacity>
            </View>

          </View>
        </View>
      </Modal>

      {/* Edit Farm Modal */}
      <Modal
        animationType="fade"
        transparent={true}
        visible={editModalVisible}
        onRequestClose={() => setEditModalVisible(false)}
      >
        <View style={styles.modalContainer}>
          <View style={[styles.modalContent, isDarkMode ? styles.darkCard : null]}>
            <Text style={[styles.modalTitle, isDarkMode ? styles.darkText : null]}>{t('Edit Farm')}</Text>
            
            <View style={styles.inputContainer}>
              <Text style={[styles.inputLabel, isDarkMode ? { color: '#CCC' } : null]}>{t('Farm Name')}</Text>
              <TextInput
                style={[styles.input, isDarkMode ? { backgroundColor: '#333', color: '#FFF', borderColor: '#444' } : null]}
                value={editName}
                onChangeText={setEditName}
                placeholder="e.g. Sunny Field"
                placeholderTextColor={isDarkMode ? "#AAA" : "#999"}
              />
            </View>

            <View style={styles.inputContainer}>
              <Text style={[styles.inputLabel, isDarkMode ? { color: '#CCC' } : null]}>{t('Area (Hectares)')}</Text>
              <TextInput
                style={[styles.input, isDarkMode ? { backgroundColor: '#333', color: '#FFF', borderColor: '#444' } : null]}
                value={editArea}
                onChangeText={setEditArea}
                placeholder="e.g. 5.5"
                placeholderTextColor={isDarkMode ? "#AAA" : "#999"}
                keyboardType="numeric"
              />
            </View>

            <View style={styles.editActionButtons}>
              <TouchableOpacity 
                style={[styles.editBtn, isDarkMode ? { backgroundColor: '#444' } : { backgroundColor: '#E0E0E0' }]} 
                onPress={() => setEditModalVisible(false)}
                disabled={isSaving}
              >
                <Text style={[styles.actionBtnText, isDarkMode ? { color: '#FFF' } : { color: '#333' }]}>{t('Cancel')}</Text>
              </TouchableOpacity>
              
              <TouchableOpacity 
                style={[styles.editBtn, { backgroundColor: '#2E7D32' }]} 
                onPress={handleEditSave}
                disabled={isSaving}
              >
                {isSaving ? (
                  <ActivityIndicator color="#FFF" size="small" />
                ) : (
                  <Text style={styles.actionBtnText}>{t('Save')}</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

    </Animated.View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: '#ffffff', marginVertical: 8, borderRadius: 12, elevation: 3, overflow: 'hidden', position: 'relative' },
  image: { width: '100%', height: 150 }, 
  imagePlaceholder: { height: 150, backgroundColor: '#f0f0f0', justifyContent: 'center', alignItems: 'center' },
  imageText: { color: '#999', marginTop: 5, fontSize: 12 },
  detailsContainer: { padding: 15 },
  titleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  title: { fontSize: 18, fontWeight: 'bold', color: '#2E7D32', flex: 1 },
  actionIconRow: { flexDirection: 'row' },
  iconButton: { padding: 8, backgroundColor: '#E8F5E9', borderRadius: 20 },
  infoRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 5 },
  infoText: { fontSize: 14, color: '#555', marginLeft: 8 },
  boldText: { fontWeight: 'bold', color: '#333' },
  uploadingOverlay: { position: 'absolute', top: 0, left: 0, right: 0, height: 150, backgroundColor: 'rgba(255,255,255,0.8)', justifyContent: 'center', alignItems: 'center', zIndex: 10 },
  uploadingText: { color: '#2E7D32', fontWeight: 'bold', marginTop: 10 },
  
  modalContainer: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', padding: 20 },
  modalContent: { backgroundColor: '#FFF', borderRadius: 15, padding: 20, position: 'relative' },
  closeButton: { position: 'absolute', top: 15, right: 15, zIndex: 1 },
  modalTitle: { fontSize: 20, fontWeight: 'bold', marginBottom: 20, color: '#333', textAlign: 'center' },
  fullImage: { width: '100%', height: 300, borderRadius: 10, marginBottom: 20 },
  actionButtons: { flexDirection: 'row', justifyContent: 'space-between', width: '100%', marginTop: 20 },
  actionBtn: { flex: 1, backgroundColor: '#2E7D32', marginHorizontal: 5, padding: 15, borderRadius: 10, alignItems: 'center', flexDirection: 'row', justifyContent: 'center' },
  actionBtnText: { color: '#FFF', fontWeight: 'bold' },
  
  // Edit Modal Styles
  inputContainer: { marginBottom: 15 },
  inputLabel: { fontSize: 14, color: '#555', marginBottom: 5, fontWeight: '500' },
  input: { borderWidth: 1, borderColor: '#DDD', borderRadius: 8, padding: 12, fontSize: 16, backgroundColor: '#F9F9F9' },
  editActionButtons: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 15 },
  editBtn: { flex: 1, padding: 15, borderRadius: 10, alignItems: 'center', marginHorizontal: 5 },
  darkCard: { backgroundColor: '#1E1E1E' },
  darkText: { color: '#FFF' }
});