# Sürüm yükseltmesinde işlem çakışması

15 Ekim 2026. Pardus 23.5 XFCE üzerinde, aynı temiz VM anlık görüntüsünden
başlayarak kurulu 0.7.0 ile yamalı paketi karşılaştırdım.

- Yamasız kaynak: `cfb3b69e8d0e9565a0803c4e90c79444ade5bf23`. Kurulu paketin
  `MainWindow.py` ve `SysActions.py` dosyaları bu kaynakla aynı.
- Canlı çakışma deneyi: `17a799748a246d8a76a53341fad439b2be1f87df`.
- Son yama: `8bcde67`. Son commit otomatik kontrolün meşgul yanıtından sonra
  zamanlanmasını koruyor; canlı deneydeki yükseltme akışını değiştirmiyor.
  Otomatik testler bu son sürümde çalıştırıldı.

## Nasıl ölçtüm?

Kurulu uygulamanın tam başlangıcını ve gerçek yardımcılarını kullandım. GTK
düğme sinyallerini [deney betiği](tools/update-live-workflow.py) üretiyor.
APT hesabı, indirme ve hazırlık işlemleri taklit edilmiyor.

Otomatik yansıda çok sayıda 404 aldığım için iki koşuda da sunucudan gelen
hedef kaynak adresini resmî `https://depopardus.itu.edu.tr` yansısına ayarladım.
Hedef Pardus 25; paket imza ve sağlama denetimleri açık.

İndirme tamamlandıktan sonra yeniden başlatma hazırlığını başlattım. Yardımcı
yeni `/etc/apt/sources.list` dosyasını yazınca SIGSTOP ile duraklattım. Bu, menü
geçişini aynı hazırlık aralığında tekrarlamak için kullanılan deney düzeni.
Ardından ayarlar → ana sayfa → yükseltme geçişini uyguladım. Süreçler, ekran
aşaması ve arşiv listesi kaydedildi. Yamasız koşudan sonra temiz görüntüye döndüm.

Betikler yalnız ayrı, geri alınabilir `pardus-update-lab` VM'i içindir; gerçek
paket kaynaklarını değiştirir ve yükseltme hazırlığı yapar.

## Sonuç

| Ölçüm | Kurulu 0.7.0 | Yamalı paket |
|---|---:|---:|
| Toplam kontrol süreci | 2 | 1 |
| Menü geçişinden önce `.deb` sayısı | 1.900 | 1.901 |
| Menü geçişinden sonra `.deb` sayısı | **0** | **1.901** |
| Dönülen aşama | `control` | `install` |
| Hazırlık sürerken meşgul durumu | Bırakılıyor | Korunuyor |

Yamasız koşuda **1.758.395.136 bayt** arşiv silindi. İkinci yardımcı önce
`apt clean` çalıştırıyor; daha sonra APT liste kilidini alamaması bu temizliği
geri almıyor. Yamalı koşuda **1.758.457.064 bayt** arşivin dosya listesi ve
toplam boyutu aynen korundu.

Yamalı kurulumun planında ek olarak 61.928 baytlık `pardus-update_0.7.0_all.deb`
yer aldı. İki listenin farkı yalnız bu dosya. Her koşunun kendi menü geçişi
öncesi ve sonrası listesi karşılaştırıldı.

- [Yamasız olay kaydı](before/events.json), [önceki arşivler](before/archives-before.json),
  [sonraki arşivler](before/archives-after.json), [hata ekranı](before/04-after-navigation.png).
- [Yamalı olay kaydı](after/events.json), [önceki arşivler](after/archives-before.json),
  [sonraki arşivler](after/archives-after.json), [korunan hazırlık ekranı](after/04-after-navigation.png).

Hazırlık duraklatılmışken `SysActions`, `AutoAptUpdate` ve `AptSourceActions`
ayrıca gerçek alt süreçler olarak başlatıldı. Üçü de **11** koduyla, arşivlere
dokunmadan çıktı. Root kilit dosyasını normal kullanıcı da açamadı.
[Çıktı](canli-kilit.log), [deney betiği](tools/update-live-lock-check.py).

## Regresyon ve paketleme

- Pardus 23 ve 25'te **24 GTK + 5 süreç testi geçti**. GTK testlerinde paket ve ağ
  işlemleri taklit ediliyor; süreç testleri geçici dosya ve gerçek alt süreç kullanıyor.
- Yamasız kodda hedefli 6 testin 4'ü yeniden giriş/durum kaybını yakaladı. İzin
  iptali ve olağan güncellemeye yönlendirme kontrol senaryoları geçti.
- `.deb` derlemesi geçti; ortak kilit modülü paketin içinde.

[Pardus 23](tests/testler-23-sonra.log) · [Pardus 25](tests/testler-25-sonra.log) ·
[Yamasız karşılaştırma](tests/gtk-once-hedefli.log) · [Derleme](tests/paket-derleme.log)

## Yeniden başlatma

Çevrimdışı kurulum deneyi sürüyor; sonucu yayımlamadan önce buraya ekleyeceğim.

Bu kayıt, forumdaki kullanıcının yaşadığı tüm sistem bozulmasının aynı sebepten
çıktığını ileri sürmüyor. Ölçülen hata, etkin hazırlığa ikinci kontrolün girmesi
ve indirilmiş arşivleri temizlemesi.
