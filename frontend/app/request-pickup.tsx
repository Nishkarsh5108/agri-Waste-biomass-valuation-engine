import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Alert, Image, ScrollView } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { API_BASE_URL } from '../constants';

export default function RequestPickupScreen() {
  const [farms, setFarms] = useState([]);
  const [selectedFarmId, setSelectedFarmId] = useState(null);
  const [image, setImage] = useState<any>(null);
  const [loadingFarms, setLoadingFarms] = useState(true);
  const [uploading, setUploading] = useState(false);
  const router = useRouter();

  useEffect(() => {
    fetchFarms();
  }, []);

  const fetchFarms = async () => {
    try {
      const userToken = await AsyncStorage.getItem('userToken');
      if (!userToken) return;

      const response = await fetch(`${API_BASE_URL}/farms/`, {
        headers: { 'Authorization': `Bearer ${userToken}` },
      });
      const data = await response.json();
      setFarms(Array.isArray(data) ? data : (data.farms || data.data || []));
    } catch (err) {
      console.error("Error fetching farms:", err);
      Alert.alert("Error", "Could not fetch farms.");
    } finally {
      setLoadingFarms(false);
    }
  };

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
      setImage(result.assets[0]);
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
      setImage(result.assets[0]);
    }
  };

  const handleSubmit = async () => {
    if (!selectedFarmId) {
      Alert.alert("Error", "Please select a farm first.");
      return;
    }
    if (!image) {
      Alert.alert("Error", "Please take or select a photo of the biomass.");
      return;
    }

    setUploading(true);
    try {
      const userToken = await AsyncStorage.getItem('userToken');
      
      const formData = new FormData();
      formData.append('farm_id', selectedFarmId);
      
      // Get filename from uri
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
          // Don't set Content-Type here, let fetch handle the boundary for multipart/form-data
        },
        body: formData,
      });

      const data = await response.json();

      if (response.ok || response.status === 201) {
        Alert.alert("Success", "Biomass pickup requested successfully! AI is processing it.");
        router.replace('/(tabs)/listings');
      } else {
        Alert.alert("Failed", data.detail || "Could not submit request.");
      }
    } catch (err) {
      console.error("Upload Error:", err);
      Alert.alert("Error", "Failed to connect to the server.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#2E7D32" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Request Pickup</Text>
        <View style={{ width: 24 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.label}>1. Select Farm</Text>
        {loadingFarms ? (
          <ActivityIndicator color="#2E7D32" />
        ) : farms.length > 0 ? (
          <View style={styles.farmList}>
            {farms.map((farm: any) => (
              <TouchableOpacity
                key={farm.id}
                style={[styles.farmItem, selectedFarmId === farm.id && styles.selectedFarmItem]}
                onPress={() => setSelectedFarmId(farm.id)}
              >
                <Text style={[styles.farmName, selectedFarmId === farm.id && styles.selectedFarmText]}>
                  {farm.name || `Farm ID: ${farm.id}`}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        ) : (
          <Text style={styles.noteText}>No farms found. Please add a farm first.</Text>
        )}

        <Text style={[styles.label, { marginTop: 20 }]}>2. Upload Photo of Biomass</Text>
        
        {image ? (
          <View style={styles.imageContainer}>
            <Image source={{ uri: image.uri }} style={styles.imagePreview} />
            <TouchableOpacity style={styles.removeImageBtn} onPress={() => setImage(null)}>
              <Ionicons name="close-circle" size={30} color="#FF5252" />
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.photoActions}>
            <TouchableOpacity style={styles.photoBtn} onPress={takePhoto}>
              <Ionicons name="camera" size={32} color="#FFF" />
              <Text style={styles.photoBtnText}>Take Photo</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.photoBtn, { backgroundColor: '#4CAF50' }]} onPress={pickImage}>
              <Ionicons name="images" size={32} color="#FFF" />
              <Text style={styles.photoBtnText}>Gallery</Text>
            </TouchableOpacity>
          </View>
        )}

        <TouchableOpacity 
          style={[styles.submitButton, (!selectedFarmId || !image || uploading) && styles.disabledButton]} 
          onPress={handleSubmit}
          disabled={!selectedFarmId || !image || uploading}
        >
          {uploading ? (
            <ActivityIndicator color="#FFF" />
          ) : (
            <Text style={styles.submitButtonText}>Submit Request</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 20, backgroundColor: '#FFF', elevation: 3, paddingTop: 50 },
  backButton: { padding: 5 },
  headerTitle: { fontSize: 20, fontWeight: 'bold', color: '#2E7D32' },
  content: { padding: 20 },
  label: { fontSize: 18, fontWeight: 'bold', color: '#333', marginBottom: 10 },
  farmList: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  farmItem: { paddingVertical: 10, paddingHorizontal: 15, backgroundColor: '#FFF', borderRadius: 20, borderWidth: 1, borderColor: '#CCC' },
  selectedFarmItem: { backgroundColor: '#2E7D32', borderColor: '#2E7D32' },
  farmName: { color: '#555', fontWeight: 'bold' },
  selectedFarmText: { color: '#FFF' },
  noteText: { color: '#777', fontStyle: 'italic' },
  photoActions: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 10 },
  photoBtn: { flex: 1, backgroundColor: '#2E7D32', marginHorizontal: 5, padding: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  photoBtnText: { color: '#FFF', marginTop: 10, fontWeight: 'bold' },
  imageContainer: { marginTop: 10, position: 'relative', alignItems: 'center' },
  imagePreview: { width: '100%', height: 250, borderRadius: 10, resizeMode: 'cover' },
  removeImageBtn: { position: 'absolute', top: -10, right: -10, backgroundColor: '#FFF', borderRadius: 15 },
  submitButton: { backgroundColor: '#E65100', padding: 15, borderRadius: 8, alignItems: 'center', marginTop: 30 },
  disabledButton: { backgroundColor: '#FFB74D' },
  submitButtonText: { color: '#FFF', fontSize: 18, fontWeight: 'bold' },
});
