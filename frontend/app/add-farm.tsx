import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import MapView, { Polygon, Marker, PROVIDER_DEFAULT } from 'react-native-maps';
import { API_BASE_URL } from '../constants';

export default function AddFarmScreen() {
  const [name, setName] = useState('');
  const [area, setArea] = useState('');
  const [loading, setLoading] = useState(false);
  const [coordinates, setCoordinates] = useState<any[]>([]);
  const router = useRouter();

  const handleMapPress = (e: any) => {
    setCoordinates([...coordinates, e.nativeEvent.coordinate]);
  };

  const clearMap = () => {
    setCoordinates([]);
  };

  const handleAddFarm = async () => {
    if (!name || !area) {
      Alert.alert("Error", "Please enter both Name and Area.");
      return;
    }

    const areaFloat = parseFloat(area);
    if (isNaN(areaFloat) || areaFloat <= 0) {
      Alert.alert("Error", "Please enter a valid number for Area.");
      return;
    }

    if (coordinates.length < 3) {
      Alert.alert("Error", "Please draw a polygon on the map with at least 3 points.");
      return;
    }

    setLoading(true);

    try {
      const userToken = await AsyncStorage.getItem('userToken');
      if (!userToken) {
        Alert.alert("Error", "Authentication token missing. Please login again.");
        router.replace('/login');
        return;
      }

      // Close the polygon by making the last coordinate same as the first one
      const geojsonCoordinates = coordinates.map(c => [c.longitude, c.latitude]);
      geojsonCoordinates.push([coordinates[0].longitude, coordinates[0].latitude]);

      const payload = {
        name: name,
        area_hectares: areaFloat,
        geojson_polygon: {
          type: "Polygon",
          coordinates: [geojsonCoordinates]
        }
      };

      const response = await fetch(`${API_BASE_URL}/farms/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${userToken}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (response.ok) {
        Alert.alert("Success", "Farm added successfully! 🌱");
        router.replace('/(tabs)/dashboard');
      } else {
        Alert.alert("Failed", data.detail || "Could not add farm.");
        console.error("Backend Error:", data);
      }
    } catch (err) {
      console.error("Fetch error:", err);
      Alert.alert("Error", "Could not connect to server.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#2E7D32" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Add New Farm</Text>
        <View style={{ width: 24 }} />
      </View>

      <View style={styles.formContainer}>
        <Text style={styles.label}>Farm Name</Text>
        <TextInput 
          style={styles.input}
          placeholder="e.g., My Wheat Field"
          value={name}
          onChangeText={setName}
        />

        <Text style={styles.label}>Area (in Hectares)</Text>
        <TextInput 
          style={styles.input}
          placeholder="e.g., 5.5"
          value={area}
          onChangeText={setArea}
          keyboardType="numeric"
        />

        <View style={styles.mapHeader}>
          <Text style={styles.label}>Draw Farm Boundary</Text>
          <TouchableOpacity onPress={clearMap}>
            <Text style={styles.clearText}>Clear</Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.noteText}>Tap on the map to add points for your farm boundary.</Text>

        <View style={styles.mapContainer}>
          <MapView
            style={styles.map}
            provider={PROVIDER_DEFAULT}
            initialRegion={{
              latitude: 28.6139,
              longitude: 77.2090,
              latitudeDelta: 0.05,
              longitudeDelta: 0.05,
            }}
            onPress={handleMapPress}
          >
            {coordinates.map((coord, index) => (
              <Marker key={index} coordinate={coord} pinColor="green" />
            ))}
            {coordinates.length > 2 && (
              <Polygon
                coordinates={coordinates}
                fillColor="rgba(46, 125, 50, 0.3)"
                strokeColor="rgba(46, 125, 50, 0.8)"
                strokeWidth={2}
              />
            )}
          </MapView>
        </View>

        {loading ? (
          <ActivityIndicator size="large" color="#2E7D32" style={{ marginTop: 20 }} />
        ) : (
          <TouchableOpacity style={styles.submitButton} onPress={handleAddFarm}>
            <Text style={styles.submitButtonText}>Save Farm</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 20, backgroundColor: '#FFF', elevation: 3, paddingTop: 50 },
  backButton: { padding: 5 },
  headerTitle: { fontSize: 20, fontWeight: 'bold', color: '#2E7D32' },
  formContainer: { padding: 20, flex: 1 },
  label: { fontSize: 16, fontWeight: '600', color: '#333', marginBottom: 5, marginTop: 15 },
  input: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#CCC', borderRadius: 8, padding: 12, fontSize: 16 },
  mapHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' },
  clearText: { color: '#E65100', fontWeight: 'bold', marginBottom: 5 },
  noteText: { color: '#777', fontSize: 12, marginBottom: 10, fontStyle: 'italic' },
  mapContainer: { flex: 1, borderRadius: 10, overflow: 'hidden', borderWidth: 1, borderColor: '#CCC', minHeight: 250 },
  map: { width: '100%', height: '100%' },
  submitButton: { backgroundColor: '#2E7D32', padding: 15, borderRadius: 8, alignItems: 'center', marginTop: 15 },
  submitButtonText: { color: '#FFF', fontSize: 18, fontWeight: 'bold' },
});