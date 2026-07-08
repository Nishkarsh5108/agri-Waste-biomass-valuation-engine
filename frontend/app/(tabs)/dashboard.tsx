import React, { useState, useEffect, useCallback, useContext } from 'react';
import { View, Text, ScrollView, ActivityIndicator, StyleSheet, TouchableOpacity, RefreshControl, Alert, Modal } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import FarmCard from '../../components/FarmCard'; 
import { API_BASE_URL } from '../../constants';
import { SettingsContext } from '../../contexts/SettingsContext';

export default function DashboardScreen() {
  const [farms, setFarms] = useState([]);
  const [totalEarnings, setTotalEarnings] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [notifModalVisible, setNotifModalVisible] = useState(false);
  const [hasUnreadNotifications, setHasUnreadNotifications] = useState(false);
  const { isDarkMode, t } = useContext(SettingsContext);
  const router = useRouter();  const fetchDashboardData = useCallback(async (isRefreshing = false) => {
    try {
      if (!isRefreshing) setLoading(true);
      setError(null);
      const userToken = await AsyncStorage.getItem('userToken'); 

      if (!userToken) {
        throw new Error('No authorization token found. Please login again.');
      }

      const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userToken}`, 
      };

      const farmsResponse = await fetch(`${API_BASE_URL}/farms/`, { method: 'GET', headers });
      
      if (farmsResponse.status === 401) {
        throw new Error('Your session has expired. Please login again.');
      }
      
      if (!farmsResponse.ok) {
        throw new Error('Failed to fetch farms data from cloud server.');
      }
      
      const farmsData = await farmsResponse.json();
      setFarms(Array.isArray(farmsData) ? farmsData : (farmsData.farms || farmsData.data || []));

      const listingsResponse = await fetch(`${API_BASE_URL}/listings/my`, { method: 'GET', headers });
      if (listingsResponse.ok) {
        const listingsData = await listingsResponse.json();
        const listingsArray = Array.isArray(listingsData) ? listingsData : (listingsData.listings || listingsData.data || []);
        
        let calculatedEarnings = 0;
        listingsArray.forEach((listing: any) => {
          if (listing.status === 'READY' && listing.estimated_tonnage) {
            calculatedEarnings += (listing.estimated_tonnage * 2000); // 2000 INR per ton
          }
        });
        setTotalEarnings(calculatedEarnings);
      }
      
    } catch (err: any) {
      console.error("Fetch error:", err);
      setError(err.message || "Could not load data.");
    } finally {
      if (!isRefreshing) setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchDashboardData(true);
  };

  if (loading) {
    return (
      <View style={[styles.center, isDarkMode ? styles.darkMainContainer : null]}>
        <ActivityIndicator size="large" color="#2E7D32" />
        <Text style={[styles.statusText, isDarkMode ? styles.darkText : null]}>{t('Loading your dashboard...')}</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={[styles.center, isDarkMode ? styles.darkMainContainer : null]}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.actionButton} onPress={() => router.replace('/login')}>
          <Text style={styles.buttonText}>{t('Go to Login')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={[styles.mainContainer, isDarkMode ? styles.darkMainContainer : null]}>
      <View style={[styles.header, isDarkMode ? styles.darkHeader : null]}>
        <Text style={[styles.headerTitle, isDarkMode ? styles.darkText : null]}>{t('Dashboard')}</Text>
        <View style={styles.headerRight}>
          <TouchableOpacity style={styles.notificationButton} onPress={() => { setNotifModalVisible(true); setHasUnreadNotifications(false); }}>
            <Ionicons name="notifications-outline" size={24} color={isDarkMode ? "#FFF" : "#333"} />
            {hasUnreadNotifications && <View style={styles.notificationBadge} />}
          </TouchableOpacity>
          <TouchableOpacity style={styles.scanButton} onPress={() => router.push('/scanner')}>
            <Ionicons name="qr-code-outline" size={20} color="#FFF" />
            <Text style={styles.scanButtonText}>{t('Scan to Pay')}</Text>
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView 
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#2E7D32']} />
        }
      >
        {/* Wallet Widget */}
        <View style={[styles.walletCard, isDarkMode ? styles.darkCard : null]}>
          <View style={styles.walletHeader}>
            <Ionicons name="wallet" size={24} color={isDarkMode ? "#4CAF50" : "#2E7D32"} />
            <Text style={[styles.walletTitle, isDarkMode ? styles.darkText : null]}>{t('Total Earnings')}</Text>
          </View>
          <Text style={[styles.walletAmount, isDarkMode ? styles.darkText : null]}>₹ {totalEarnings.toLocaleString('en-IN')}</Text>
          <Text style={styles.walletSubtext}>{t('From processed biomass pickups')}</Text>
        </View>

        {/* Market Trends Widget */}
        <View style={[styles.marketWidget, isDarkMode ? styles.darkCard : null]}>
          <View style={styles.marketHeader}>
            <Ionicons name="trending-up" size={24} color={isDarkMode ? "#64B5F6" : "#1976D2"} />
            <Text style={[styles.marketTitle, isDarkMode ? styles.darkText : null]}>{t('Market Trends')}</Text>
          </View>
          <View style={styles.marketRow}>
            <Text style={[styles.marketItem, isDarkMode ? { color: '#CCC' } : null]}>{t('Corn Stover')}</Text>
            <Text style={[styles.marketPrice, isDarkMode ? styles.darkText : null]}>₹2,000 / ton <Text style={styles.trendUp}>▲ 2%</Text></Text>
          </View>
          <View style={styles.marketRow}>
            <Text style={[styles.marketItem, isDarkMode ? { color: '#CCC' } : null]}>{t('Wheat Straw')}</Text>
            <Text style={[styles.marketPrice, isDarkMode ? styles.darkText : null]}>₹1,850 / ton <Text style={styles.trendDown}>▼ 1%</Text></Text>
          </View>
        </View>

        <Text style={[styles.sectionTitle, isDarkMode ? styles.darkText : null]}>{t('My Farms')}</Text>

        {farms.length > 0 ? (
          <View>
            {farms.map((farm: any) => (
              <FarmCard key={farm.id} data={farm} onRefreshDashboard={() => fetchDashboardData(true)} />
            ))}
          </View>
        ) : (
          <View style={styles.emptyCenter}>
            <Text style={[styles.statusText, isDarkMode ? { color: '#CCC' } : null]}>{t('No farms found for this account.')}</Text>
          </View>
        )}
      </ScrollView>

      <TouchableOpacity 
        style={styles.fab} 
        onPress={() => router.push('/add-farm')}
      >
        <Text style={styles.fabText}>{t('+ Add Farm')}</Text>
      </TouchableOpacity>

      {/* Notifications Modal */}
      <Modal visible={notifModalVisible} transparent={true} animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, isDarkMode ? styles.darkCard : null]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, isDarkMode ? styles.darkText : null]}>{t('Notifications')}</Text>
              <TouchableOpacity onPress={() => setNotifModalVisible(false)}>
                <Ionicons name="close" size={24} color={isDarkMode ? "#FFF" : "#333"} />
              </TouchableOpacity>
            </View>
            <View style={styles.emptyCenter}>
              <Ionicons name="notifications-off-outline" size={48} color={isDarkMode ? "#666" : "#CCC"} />
              <Text style={[styles.statusText, isDarkMode ? { color: '#CCC' } : null]}>{t('No new notifications.')}</Text>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  mainContainer: { flex: 1, backgroundColor: '#f5f5f5' },
  header: { padding: 20, paddingTop: 50, backgroundColor: '#FFF', elevation: 3, borderBottomWidth: 1, borderBottomColor: '#E0E0E0', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  headerTitle: { fontSize: 22, fontWeight: 'bold', color: '#2E7D32' },
  headerRight: { flexDirection: 'row', alignItems: 'center' },
  notificationButton: { marginRight: 15, position: 'relative' },
  notificationBadge: { position: 'absolute', top: -2, right: -2, backgroundColor: 'red', width: 10, height: 10, borderRadius: 5, borderWidth: 1, borderColor: '#FFF' },
  scanButton: { flexDirection: 'row', backgroundColor: '#2E7D32', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, alignItems: 'center' },
  scanButtonText: { color: '#FFF', fontWeight: 'bold', marginLeft: 5 },
  scrollContent: { padding: 15, paddingBottom: 90 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20, backgroundColor: '#f5f5f5' },
  emptyCenter: { justifyContent: 'center', alignItems: 'center', padding: 20, marginTop: 50 },
  statusText: { marginTop: 10, fontSize: 16, color: '#333', textAlign: 'center' },
  errorText: { color: '#D32F2F', fontSize: 16, marginBottom: 20, textAlign: 'center' },
  darkMainContainer: { backgroundColor: '#121212' },
  darkHeader: { backgroundColor: '#1E1E1E', borderBottomColor: '#333' },
  darkCard: { backgroundColor: '#1E1E1E' },
  darkText: { color: '#FFF' },
  darkBorder: { borderBottomColor: '#333' },
  actionButton: { backgroundColor: '#2E7D32', paddingVertical: 12, paddingHorizontal: 25, borderRadius: 8, marginTop: 15 },
  buttonText: { color: '#FFF', fontWeight: 'bold', fontSize: 16 },
  fab: { position: 'absolute', bottom: 20, right: 20, backgroundColor: '#2E7D32', paddingVertical: 15, paddingHorizontal: 20, borderRadius: 30, elevation: 5, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.3, shadowRadius: 3 },
  fabText: { color: 'white', fontWeight: 'bold', fontSize: 16 },
  
  walletCard: { backgroundColor: '#FFF', padding: 20, borderRadius: 15, marginBottom: 20, elevation: 3, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4 },
  walletHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 10 },
  walletTitle: { fontSize: 16, fontWeight: 'bold', color: '#555', marginLeft: 8 },
  walletAmount: { fontSize: 32, fontWeight: 'bold', color: '#2E7D32' },
  walletSubtext: { fontSize: 12, color: '#888', marginTop: 5 },
  sectionTitle: { fontSize: 18, fontWeight: 'bold', color: '#333', marginBottom: 10 },
  
  marketWidget: { backgroundColor: '#FFF', padding: 20, borderRadius: 15, marginBottom: 20, elevation: 3, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4 },
  marketHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 15 },
  marketTitle: { fontSize: 16, fontWeight: 'bold', color: '#555', marginLeft: 8 },
  marketRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10, borderBottomWidth: 1, borderBottomColor: '#F0F0F0', paddingBottom: 5 },
  marketItem: { fontSize: 14, color: '#333', fontWeight: '500' },
  marketPrice: { fontSize: 14, fontWeight: 'bold', color: '#555' },
  trendUp: { color: '#2E7D32', fontSize: 12 },
  trendDown: { color: '#D32F2F', fontSize: 12 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 20 },
  modalContent: { backgroundColor: '#FFF', padding: 25, borderRadius: 15 },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15 },
  modalTitle: { fontSize: 18, fontWeight: 'bold', color: '#2E7D32' },
  paymentButton: { backgroundColor: '#1976D2', paddingVertical: 12, borderRadius: 8, marginBottom: 10, alignItems: 'center' },
  paymentButtonText: { color: '#FFF', fontWeight: 'bold', fontSize: 16 },
});