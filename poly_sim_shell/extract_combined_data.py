import sys
import os
import glob
import csv

def build_combined_csv(log_dir, output_file):
    pattern = os.path.join(log_dir, "sim_log_5M_*.csv")
    files = sorted(glob.glob(pattern))
    
    if not files:
        print(f"No files matching 'sim_log_5M_*.csv' found in {log_dir}")
        return

    print(f"Found {len(files)} log files. Combining them into '{output_file}'...")

    total_rows = 0
    with open(output_file, 'w', newline='', encoding='utf-8') as out_f:
        writer = csv.writer(out_f)
        # Write the header requested by the user
        writer.writerow(["DateTime", "BTC_Price", "Window_Open_Price", "UP_Bid", "DN_Bid"])
        
        for f in files:
            try:
                # Use errors='replace' to avoid utf-8 decode errors on old broken logs
                with open(f, 'r', encoding='utf-8', errors='replace') as in_f:
                    reader = csv.reader(in_f)
                    header = next(reader, None)
                    
                    for row in reader:
                        if not row: continue
                        if row[0] == "TRADE_EVENT": continue
                        
                        try:
                            # From the known sim log structure:
                            # 0: Timestamp (DateTime)
                            # 6: BTC_Price
                            # 7: BTC_Open (Window Open Price, exactly what the user requested, resets at the 5 min mark)
                            # 22: UP_Bid
                            # 23: DN_Bid
                            
                            timestamp = row[0]
                            btc_price = row[6]
                            window_open = row[7]
                            up_bid = row[22]
                            dn_bid = row[23]
                            
                            writer.writerow([timestamp, btc_price, window_open, up_bid, dn_bid])
                            total_rows += 1
                        except IndexError:
                            continue
            except Exception as e:
                print(f"Error reading {f}: {e}")
                
    print(f"\nSuccessfully extracted and wrote {total_rows} rows to {output_file}.")

if __name__ == "__main__":
    log_directory = "logs"
    output_filename = "combined_5m_data.csv"
    build_combined_csv(log_directory, output_filename)
