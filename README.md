
# ISCP 2025 - Project Guardian 2.0 (SOC Challange)

# Author
Smit Verma <br>
CTFd Username : smitvermawork <br>
Email ID : smitvermawork@gmail.com
# Redaction Methodology
1. I have opted for a hybrid masking methodology for securing PII.
2. Each PII is secured with appropriate masking, prefixed with the data type of value being masked : `<DataType_MaskedData>`
	- This prefixing allows for easy data-type recognition for both human readability and automation.

3. For e-mails, the redaction pattern is : `<DataType_FirstLetter>XXX@<FirstLetterOfDomain>XXX.TLD`

	For example,
	
	| Original Value              | Redacted Value    |
	| --------------------------- | ----------------- |
	| `we@domain.com`             | `wXXX@dXXX.com` |
	| `mynameisdavid@davidcafe.in`  | `mXXX@dXXX.com` |

	- This fixed length redaction allows for few benefits :
		-  **Enhanced Privacy**: Hides actual username length, reducing re-identification risk (especially for very short usernames)
		-  **Consistency**: Uniform format across entries improves log structure and readability.  
		-  **Readability**: Easier for humans to scan and interpret logs quickly.
		-  **Automation-Friendly**: Simplifies pattern matching, filtering, and parsing in scripts.
	- Due to the various custom domains found in the data, domain has also been masked to prevent any identity leakage.
	
<br>

  4. For UPI IDs, the redaction pattern is : `<DataType_FirstLetter>XXX@<FinancialProvider>`
   
		| Original Value              | Redacted Value |
		| --------------------------- | -------------- |
		| `r@okhdfc`                  | `rXXX@okhdfc`  |
		| `deepakumariverma123@oksbi` | `dXXX@oksbi`   |
# Error Handling in Logs
- Sometimes, logs can contain error in JSON or CSV that can lead to parser crashes. 
- To handle such cases, I have implemented error-handling that defaults to full redaction of `data_json` field, based on the principle : A lost log entry is less damaging than PII data leak.
- The operator is also alerted through a custom print message, mentioning the error and the corresponding record number for manual inspection.
