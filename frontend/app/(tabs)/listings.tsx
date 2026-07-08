import React, { useState, useEffect, useCallback, useContext } from 'react';
import { View, Text, ScrollView, ActivityIndicator, StyleSheet, TouchableOpacity, RefreshControl, Linking, Modal, Alert, TextInput } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import MapView, { Marker, Polyline } from 'react-native-maps';
import { API_BASE_URL } from '../../constants';
import { SettingsContext } from '../../contexts/SettingsContext';

export default function ListingsScreen() {
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  
  // Logistics Connection States
  const [searchModalVisible, setSearchModalVisible] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [assignedDriver, setAssignedDriver] = useState<any>(null);
  const [currentRoute, setCurrentRoute] = useState<any>(null);
  const [activeListingId, setActiveListingId] = useState<number | null>(null);
  
  // Rating States
  const [ratingModalVisible, setRatingModalVisible] = useState(false);
  const [rating, setRating] = useState(5);
  const [feedback, setFeedback] = useState('');
  const [isSubmittingRating, setIsSubmittingRating] = useState(false);

  const { isDarkMode, t } = useContext(SettingsContext);
  const router = useRouter();

  const fetchListings = useCallback(async (isRefreshing = false) => {
    try {
      if (!isRefreshing) setLoading(true);
      const userToken = await AsyncStorage.getItem('userToken'); 
      if (!userToken) {
        throw new Error('No authorization token found. Please login again.');
      }

      const response = await fetch(`${API_BASE_URL}/listings/my`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${userToken}`, 
        },
      });
      
      if (response.status === 401) {
        throw new Error('Your session has expired. Please login again.');
      }
      
      if (!response.ok) {
        throw new Error('Failed to fetch listings data from server.');
      }
      
      const data = await response.json();
      setListings(Array.isArray(data) ? data : (data.listings || data.data || []));
      setError(null);
    } catch (err: any) {
      console.error("Fetch error:", err);
      setError(err.message || "Could not load listings.");
    } finally {
      if (!isRefreshing) setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchListings();
    const interval = setInterval(() => fetchListings(true), 10000); 
    return () => clearInterval(interval);
  }, [fetchListings]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchListings(true);
  };

  const handleFindTractor = async (listingId: number) => {
    setSearchModalVisible(true);
    setIsSearching(true);
    setAssignedDriver(null);
    setCurrentRoute(null);
    setActiveListingId(listingId);
    
    try {
      const userToken = await AsyncStorage.getItem('userToken');
      const response = await fetch(`${API_BASE_URL}/logistics/tractor/${listingId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${userToken}`,
          'Content-Type': 'application/json'
        },
      });
      
      const data = await response.json();
      
      // Artificial delay for UI effect
      setTimeout(() => {
        setIsSearching(false);
        if (response.ok && data.tractor) {
          setAssignedDriver(data.tractor);
          setCurrentRoute(data.route);
        } else {
          Alert.alert("Status", data.message || "Could not locate tractor at this time.");
          setSearchModalVisible(false);
        }
      }, 2000);
      
    } catch (err) {
      setIsSearching(false);
      setSearchModalVisible(false);
      Alert.alert("Error", "Network error while searching for tractor.");
    }
  };

  const handleCompletePickup = () => {
    setSearchModalVisible(false);
    setRatingModalVisible(true);
  };

  const submitRating = async () => {
    if (!activeListingId) return;
    setIsSubmittingRating(true);
    try {
      const userToken = await AsyncStorage.getItem('userToken');
      const response = await fetch(`${API_BASE_URL}/logistics/tractor/${activeListingId}/rate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${userToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ rating, feedback })
      });
      
      if (response.ok) {
        Alert.alert("Success", "Thank you! Your feedback has been recorded and the pickup is complete.");
        setRatingModalVisible(false);
        setRating(5);
        setFeedback('');
        fetchListings(true);
      } else {
        const errorData = await response.json();
        Alert.alert("Error", errorData.detail || "Failed to submit rating.");
      }
    } catch (err) {
      Alert.alert("Error", "Network error while submitting rating.");
    } finally {
      setIsSubmittingRating(false);
    }
  };

  const handleDeleteListing = (listingId: number) => {
    Alert.alert(
      "Delete Request",
      "Are you sure you want to delete this biomass request?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              const userToken = await AsyncStorage.getItem('userToken');
              const res = await fetch(`${API_BASE_URL}/listings/${listingId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${userToken}` },
              });
              if (res.ok) {
                fetchListings(true);
              } else {
                Alert.alert("Error", "Failed to delete request.");
              }
            } catch (e) {
              Alert.alert("Error", "Network error occurred.");
            }
          }
        }
      ]
    );
  };

  if (loading && listings.length === 0) {
    return (
      <View style={[styles.center, isDarkMode ? styles.darkMainContainer : null]}>
        <ActivityIndicator size="large" color="#2E7D32" />
        <Text style={[styles.statusText, isDarkMode ? styles.darkText : null]}>Loading your requests...</Text>
      </View>
    );
  }

  return (
    <View style={[styles.mainContainer, isDarkMode ? styles.darkMainContainer : null]}>
      <View style={[styles.header, isDarkMode ? styles.darkHeader : null]}>
        <Text style={[styles.headerTitle, isDarkMode ? styles.darkText : null]}>{t('My Biomass Requests')}</Text>
      </View>
      
      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      <ScrollView 
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#2E7D32']} />
        }
      >
        {listings.length > 0 ? (
          listings.map((listing: any) => (
            <View key={listing.id || Math.random().toString()} style={[styles.card, isDarkMode ? styles.darkCard : null]}>
              <View style={styles.cardHeader}>
                <Text style={[styles.farmId, isDarkMode ? styles.darkText : null]}>{t('Farm ID:')} {listing.farm_id}</Text>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <View style={[styles.statusBadge, { backgroundColor: listing.status === 'READY' ? (isDarkMode ? '#1b5e20' : '#E8F5E9') : (isDarkMode ? '#e65100' : '#FFF3E0'), marginRight: 10 }]}>
                    <Text style={[styles.statusTextBadge, { color: listing.status === 'READY' ? (isDarkMode ? '#FFF' : '#2E7D32') : (isDarkMode ? '#FFF' : '#E65100') }]}>
                      {listing.status ? t(listing.status) : t('PROCESSING')}
                    </Text>
                  </View>
                  <TouchableOpacity onPress={() => handleDeleteListing(listing.id)} style={{ padding: 5 }}>
                    <Ionicons name="trash" size={20} color="#D32F2F" />
                  </TouchableOpacity>
                </View>
              </View>
              
              {listing.status === 'READY' ? (
                <View style={[styles.resultsContainer, isDarkMode ? { backgroundColor: '#2e3b32' } : null]}>
                  <Text style={[styles.resultLabel, isDarkMode ? { color: '#CCC' } : null]}>{t('Est. Tonnage:')} <Text style={[styles.resultValue, isDarkMode ? { color: '#81C784' } : null]}>{listing.estimated_tonnage}t</Text></Text>
                  <Text style={[styles.resultLabel, isDarkMode ? { color: '#CCC' } : null]}>{t('Quality Score:')} <Text style={[styles.resultValue, isDarkMode ? { color: '#81C784' } : null]}>{listing.quality_score ? (listing.quality_score * 10).toFixed(1) : 0}/10</Text></Text>
                  <Text style={[styles.resultLabel, isDarkMode ? { color: '#CCC' } : null]}>{t('CV Density Ratio:')} <Text style={[styles.resultValue, isDarkMode ? { color: '#81C784' } : null]}>{listing.cv_density_ratio}</Text></Text>
                  {listing.estimated_tonnage != null ? (
                    <Text style={[styles.resultLabel, isDarkMode ? { color: '#CCC' } : null]}>
                      {t('Estimated Payout:')} <Text style={[styles.resultValue, isDarkMode ? { color: '#81C784' } : null]}>₹ {(listing.estimated_tonnage * 2000).toLocaleString('en-IN')}</Text>
                    </Text>
                  ) : null}
                  
                  {/* Find Tractor Button */}
                  <TouchableOpacity 
                    style={styles.findTractorButton} 
                    onPress={() => handleFindTractor(listing.id)}
                  >
                    <Ionicons name="search" size={16} color="#FFF" />
                    <Text style={styles.findTractorButtonText}>{t('Find Nearest Tractor')}</Text>
                  </TouchableOpacity>
                </View>
              ) : (
                <View style={[styles.processingContainer, isDarkMode ? { backgroundColor: '#4e2809' } : null]}>
                  <ActivityIndicator size="small" color={isDarkMode ? "#FFB74D" : "#E65100"} />
                  <Text style={[styles.processingText, isDarkMode ? { color: '#FFB74D' } : null]}>{t('AI is analyzing your images...')}</Text>
                </View>
              )}
            </View>
          ))
        ) : (
          <View style={styles.emptyCenter}>
            <Ionicons name="leaf-outline" size={64} color={isDarkMode ? "#555" : "#CCC"} />
            <Text style={[styles.statusText, isDarkMode ? { color: '#CCC' } : null]}>{t('No biomass requests found.')}</Text>
            <Text style={[styles.subText, isDarkMode ? { color: '#888' } : null]}>{t('Tap the + button to request a pickup.')}</Text>
          </View>
        )}
      </ScrollView>

      {/* Floating Action Button */}
      <TouchableOpacity 
        style={styles.fab} 
        onPress={() => router.push('/request-pickup')}
      >
        <Text style={styles.fabText}>{t('+ Request Pickup')}</Text>
      </TouchableOpacity>

      {/* Logistics Tracking Modal */}
      <Modal
        animationType="slide"
        transparent={true}
        visible={searchModalVisible}
        onRequestClose={() => setSearchModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, isDarkMode ? styles.darkCard : null]}>
            
            <TouchableOpacity style={styles.closeButton} onPress={() => setSearchModalVisible(false)}>
              <Ionicons name="close" size={28} color={isDarkMode ? "#FFF" : "#333"} />
            </TouchableOpacity>

            {isSearching ? (
              <View style={styles.searchingContainer}>
                <ActivityIndicator size="large" color="#F57C00" />
                <Text style={styles.searchingTitle}>{t('Searching Dispatch...')}</Text>
                <Text style={[styles.searchingText, isDarkMode ? { color: '#CCC' } : null]}>{t('Locating the nearest available tractor for your biomass pickup.')}</Text>
              </View>
            ) : (
              <View style={styles.driverFoundContainer}>
                <View style={styles.successIconContainer}>
                  <Ionicons name="checkmark-circle" size={60} color={isDarkMode ? "#4CAF50" : "#2E7D32"} />
                </View>
                <Text style={[styles.driverFoundTitle, isDarkMode ? { color: '#81C784' } : null]}>{t('Tractor Dispatched!')}</Text>
                
                <View style={[styles.driverCard, isDarkMode ? { backgroundColor: '#222', borderColor: '#444' } : null]}>
                  <View style={[styles.driverHeader, isDarkMode ? { borderBottomColor: '#444' } : null]}>
                    <View style={styles.driverAvatar}>
                      <Ionicons name="person" size={30} color="#666" />
                    </View>
                    <View style={styles.driverInfo}>
                      <Text style={[styles.driverName, isDarkMode ? styles.darkText : null]}>{assignedDriver?.name}</Text>
                      <View style={styles.ratingRow}>
                        <Ionicons name="star" size={14} color="#FFB300" />
                        <Text style={[styles.ratingText, isDarkMode ? { color: '#CCC' } : null]}>{assignedDriver?.rating}</Text>
                      </View>
                    </View>
                  </View>
                  
                  <View style={styles.driverDetailRow}>
                    <Ionicons name="bus" size={18} color={isDarkMode ? "#AAA" : "#555"} />
                    <Text style={[styles.driverDetailText, isDarkMode ? { color: '#CCC' } : null]}>{assignedDriver?.vehicle}</Text>
                  </View>
                  <View style={styles.driverDetailRow}>
                    <Ionicons name="time" size={18} color="#D84315" />
                    <Text style={[styles.driverDetailText, isDarkMode ? { color: '#CCC' } : null]}>{t('ETA:')} <Text style={styles.etaText}>{assignedDriver?.eta}</Text></Text>
                  </View>
                </View>

                {currentRoute && (
                  <View style={styles.mapContainer}>
                    <MapView
                      style={styles.map}
                      initialRegion={{
                        latitude: currentRoute.current.latitude,
                        longitude: currentRoute.current.longitude,
                        latitudeDelta: Math.abs(currentRoute.depot.latitude - currentRoute.farm.latitude) * 2 || 0.05,
                        longitudeDelta: Math.abs(currentRoute.depot.longitude - currentRoute.farm.longitude) * 2 || 0.05,
                      }}
                    >
                      <Marker coordinate={currentRoute.depot} title="Depot">
                        <Ionicons name="business" size={24} color="#555" />
                      </Marker>
                      <Marker coordinate={currentRoute.farm} title="Farm">
                        <Ionicons name="leaf" size={24} color="#2E7D32" />
                      </Marker>
                      <Marker coordinate={currentRoute.current} title="Tractor">
                        <View style={styles.tractorMarker}>
                          <Ionicons name="bus" size={16} color="#FFF" />
                        </View>
                      </Marker>
                      <Polyline
                        coordinates={[currentRoute.depot, currentRoute.current, currentRoute.farm]}
                        strokeColor="#F57C00"
                        strokeWidth={3}
                        lineDashPattern={[5, 5]}
                      />
                    </MapView>
                  </View>
                )}
                
                <TouchableOpacity 
                  style={styles.callDriverButton} 
                  onPress={() => Linking.openURL(`tel:${assignedDriver?.phone}`)}
                >
                  <Ionicons name="call" size={20} color="#FFF" />
                  <Text style={styles.callDriverText}>{t('Call Driver')}</Text>
                </TouchableOpacity>
                
                <TouchableOpacity style={[styles.completeBtn, isDarkMode ? { backgroundColor: '#333' } : null]} onPress={handleCompletePickup}>
                  <Text style={[styles.completeBtnText, isDarkMode ? { color: '#81C784' } : null]}>{t('Complete Pickup')}</Text>
                </TouchableOpacity>
              </View>
            )}

          </View>
        </View>
      </Modal>

    {/* Driver Rating Modal */}
      <Modal
        animationType="fade"
        transparent={true}
        visible={ratingModalVisible}
        onRequestClose={() => setRatingModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, isDarkMode ? styles.darkCard : null]}>
            
            <TouchableOpacity style={styles.closeButton} onPress={() => setRatingModalVisible(false)}>
              <Ionicons name="close" size={28} color={isDarkMode ? "#FFF" : "#333"} />
            </TouchableOpacity>

            <Text style={[styles.driverFoundTitle, isDarkMode ? { color: '#81C784' } : null]}>{t('Rate Your Pickup')}</Text>
            <Text style={[styles.subText, isDarkMode ? { color: '#CCC' } : null]}>{t('How was your experience with ')}{assignedDriver?.name}?</Text>

            <View style={styles.starsContainer}>
              {[1, 2, 3, 4, 5].map((star) => (
                <TouchableOpacity key={star} onPress={() => setRating(star)}>
                  <Ionicons 
                    name={star <= rating ? "star" : "star-outline"} 
                    size={40} 
                    color="#FFB300" 
                    style={styles.starIcon}
                  />
                </TouchableOpacity>
              ))}
            </View>

            <TextInput
              style={[styles.feedbackInput, isDarkMode ? { backgroundColor: '#333', color: '#FFF', borderColor: '#444' } : null]}
              placeholder={t('Leave a comment (optional)')}
              placeholderTextColor={isDarkMode ? "#AAA" : "#999"}
              value={feedback}
              onChangeText={setFeedback}
              multiline={true}
            />

            <TouchableOpacity 
              style={[styles.actionBtn, { marginTop: 20 }]} 
              onPress={submitRating}
              disabled={isSubmittingRating}
            >
              {isSubmittingRating ? (
                <ActivityIndicator color="#FFF" size="small" />
              ) : (
                <Text style={styles.actionBtnText}>{t('Submit Rating')}</Text>
              )}
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
  scrollContent: { padding: 15, paddingBottom: 100 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyCenter: { justifyContent: 'center', alignItems: 'center', marginTop: 50 },
  statusText: { marginTop: 10, fontSize: 16, color: '#666', textAlign: 'center' },
  subText: { marginTop: 5, fontSize: 14, color: '#999', textAlign: 'center' },
  errorText: { color: '#D8000C', fontSize: 14, textAlign: 'center', marginTop: 10 },
  card: { backgroundColor: '#FFF', borderRadius: 10, padding: 15, marginBottom: 15, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.2, shadowRadius: 2 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  farmId: { fontSize: 16, fontWeight: 'bold', color: '#333' },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12 },
  statusTextBadge: { fontSize: 12, fontWeight: 'bold' },
  resultsContainer: { marginTop: 10, backgroundColor: '#F1F8E9', padding: 10, borderRadius: 8 },
  resultLabel: { fontSize: 14, color: '#555', marginBottom: 5 },
  resultValue: { fontWeight: 'bold', color: '#2E7D32' },
  processingContainer: { flexDirection: 'row', alignItems: 'center', marginTop: 10, padding: 10, backgroundColor: '#FFF3E0', borderRadius: 8 },
  processingText: { marginLeft: 10, color: '#E65100', fontStyle: 'italic', fontSize: 14 },
  fab: { position: 'absolute', bottom: 20, right: 20, backgroundColor: '#2E7D32', paddingVertical: 15, paddingHorizontal: 20, borderRadius: 30, elevation: 5, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.3, shadowRadius: 3, flexDirection: 'row', alignItems: 'center' },
  fabText: { color: 'white', fontWeight: 'bold', fontSize: 16 },
  
  // New Find Tractor Button
  findTractorButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#F57C00', paddingVertical: 12, borderRadius: 8, marginTop: 15, elevation: 2 },
  findTractorButtonText: { color: '#FFF', fontWeight: 'bold', marginLeft: 8, fontSize: 15 },
  
  // Modal Styles
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', padding: 20 },
  modalContent: { backgroundColor: '#FFF', borderRadius: 15, padding: 25, alignItems: 'center', position: 'relative', elevation: 5 },
  closeButton: { position: 'absolute', top: 15, right: 15, zIndex: 1 },
  
  // Searching State
  searchingContainer: { alignItems: 'center', paddingVertical: 30 },
  searchingTitle: { fontSize: 20, fontWeight: 'bold', color: '#F57C00', marginTop: 20, marginBottom: 10 },
  searchingText: { textAlign: 'center', color: '#666', paddingHorizontal: 10 },
  
  // Driver Found State
  driverFoundContainer: { width: '100%', alignItems: 'center' },
  successIconContainer: { marginBottom: 10 },
  driverFoundTitle: { fontSize: 22, fontWeight: 'bold', color: '#2E7D32', marginBottom: 20 },
  driverCard: { width: '100%', backgroundColor: '#F5F5F5', borderRadius: 12, padding: 15, marginBottom: 20, borderWidth: 1, borderColor: '#E0E0E0' },
  driverHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 15, borderBottomWidth: 1, borderBottomColor: '#DDD', paddingBottom: 10 },
  driverAvatar: { width: 50, height: 50, borderRadius: 25, backgroundColor: '#E0E0E0', justifyContent: 'center', alignItems: 'center', marginRight: 15 },
  driverInfo: { flex: 1 },
  driverName: { fontSize: 18, fontWeight: 'bold', color: '#333' },
  ratingRow: { flexDirection: 'row', alignItems: 'center', marginTop: 2 },
  ratingText: { marginLeft: 4, fontWeight: 'bold', color: '#555', fontSize: 14 },
  driverDetailRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  driverDetailText: { marginLeft: 10, fontSize: 15, color: '#444' },
  etaText: { fontWeight: 'bold', color: '#D84315' },
  
  callDriverButton: { flexDirection: 'row', width: '100%', alignItems: 'center', justifyContent: 'center', backgroundColor: '#2E7D32', paddingVertical: 14, borderRadius: 10, elevation: 2, marginBottom: 10 },
  callDriverText: { color: '#FFF', fontWeight: 'bold', marginLeft: 8, fontSize: 16 },
  completeBtn: { width: '100%', alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFF', borderColor: '#2E7D32', borderWidth: 1, paddingVertical: 14, borderRadius: 10 },
  completeBtnText: { color: '#2E7D32', fontWeight: 'bold', fontSize: 16 },
  
  // Map styles
  mapContainer: { width: '100%', height: 200, borderRadius: 12, overflow: 'hidden', marginBottom: 15, borderWidth: 1, borderColor: '#DDD' },
  map: { width: '100%', height: '100%' },
  tractorMarker: { backgroundColor: '#F57C00', padding: 5, borderRadius: 20, borderWidth: 2, borderColor: '#FFF', shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.3, shadowRadius: 2, elevation: 3 },
  
  // Rating styles
  starsContainer: { flexDirection: 'row', justifyContent: 'center', marginVertical: 20 },
  starIcon: { marginHorizontal: 5 },
  feedbackInput: { width: '100%', borderWidth: 1, borderColor: '#DDD', borderRadius: 10, padding: 15, minHeight: 100, textAlignVertical: 'top', fontSize: 16, backgroundColor: '#F9F9F9' },
  actionBtn: { width: '100%', backgroundColor: '#F57C00', paddingVertical: 15, borderRadius: 10, alignItems: 'center', justifyContent: 'center', elevation: 2 },
  actionBtnText: { color: '#FFF', fontWeight: 'bold', fontSize: 16 },
  darkMainContainer: { backgroundColor: '#121212' },
  darkHeader: { backgroundColor: '#1E1E1E', borderBottomColor: '#333' },
  darkCard: { backgroundColor: '#1E1E1E' },
  darkText: { color: '#FFF' },
  darkBorder: { borderBottomColor: '#333' }
});
