# Referensi: pola yang sama di Java (Spring AI)

Kerangka ini menunjukkan bahwa pola workshop (tool berparameter + agent loop + model lokal)
bisa diterapkan di stack Java/Spring Boot. Kode ini **kerangka**, bukan proyek siap jalan:
sesuaikan versi Spring AI, nama view, dan modul hak akses aplikasi Anda.
Diverifikasi terhadap dokumentasi Spring AI 2.0.x (Oktober 2026).

> **Prasyarat:** Spring AI dan LangChain4j membutuhkan **Java 17+** (Spring AI 2.x berbasis Spring Boot 4).
> Aplikasi lama (mis. Java 6/8, Spring Boot 1.x) tidak perlu dimigrasi lebih dulu: buat **layanan AI terpisah**
> (Spring Boot baru) yang dipanggil aplikasi lama lewat REST, dengan identitas/hak akses user diteruskan.

## Dependency (Maven)

```xml
<dependency>
  <groupId>org.springframework.ai</groupId>
  <artifactId>spring-ai-starter-model-ollama</artifactId>
</dependency>
```

## Konfigurasi (`application.yml`)

```yaml
spring:
  ai:
    ollama:
      base-url: http://localhost:11434
      chat:
        model: qwen3:8b
  datasource:
    url: jdbc:postgresql://localhost:5433/erp
    username: erp_ai_readonly      # role read-only, sama seperti workshop
    password: ${ERP_AI_DB_PASSWORD}
```

## Tool = method dengan anotasi `@Tool`

```java
@Component
class PenjualanTools {

    private final JdbcTemplate jdbc;          // memakai koneksi role read-only
    private final HakAksesService hakAkses;   // modul hak akses ERP yang sudah ada

    PenjualanTools(JdbcTemplate jdbc, HakAksesService hakAkses) {
        this.jdbc = jdbc;
        this.hakAkses = hakAkses;
    }

    @Tool(description = "Data penjualan per bulan (qty dan nilai rupiah) untuk satu produk. "
                      + "Gunakan untuk pertanyaan tentang tren penjualan.")
    List<Map<String, Object>> trenPenjualan(
            @ToolParam(description = "Nama produk, mis. 'Biskuit Kelapa'") String produk,
            @ToolParam(description = "Jumlah bulan ke belakang (1-18)", required = false) Integer bulanTerakhir) {

        hakAkses.wajibPunya("penjualan");      // izin dicek oleh KODE, bukan oleh prompt
        int n = bulanTerakhir == null ? 3 : Math.max(1, Math.min(bulanTerakhir, 18));

        return jdbc.queryForList("""
            SELECT to_char(bulan, 'YYYY-MM') AS bulan, sum(qty) AS qty, round(sum(nilai)) AS nilai
            FROM ai.v_penjualan
            WHERE produk ILIKE ?
              AND bulan > (SELECT tanggal_posisi FROM ai.v_info) - make_interval(months => ?)
            GROUP BY bulan ORDER BY bulan
            """, "%" + produk + "%", n);       // query berparameter
    }
}
```

## Endpoint asisten

```java
@RestController
class AsistenController {

    private final ChatClient chat;

    AsistenController(ChatClient.Builder builder, PenjualanTools penjualanTools) {
        this.chat = builder
            .defaultSystem("Kamu asisten ERP. Semua angka wajib dari tool. Jawab ringkas dalam bahasa Indonesia.")
            .defaultTools(penjualanTools)
            .build();
    }

    @PostMapping("/api/asisten")
    String tanya(@RequestBody String pertanyaan) {
        return chat.prompt().user(pertanyaan).call().content();
    }
}
```

Spring AI menjalankan agent loop (model → tool → model) secara otomatis. Panel chat di Angular
cukup memanggil endpoint ini; untuk menampilkan langkah agent seperti di demo, catat setiap
pemanggilan tool (mis. lewat logging/observability) lalu kirim ke layar.

## Catatan untuk model Qwen3 di Ollama

Model "berpikir" (thinking) memperlambat jawaban. Di Spring AI, mode berpikir dapat dimatikan
lewat `OllamaChatOptions.builder().disableThinking()`.

## Alternatif

LangChain4j juga menyediakan anotasi `@Tool` dan `AiServices` dengan pola yang serupa.
