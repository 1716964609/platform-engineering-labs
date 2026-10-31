{{- define "platform-common.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name | quote }}
app.kubernetes.io/instance: {{ .Release.Name | quote }}
platform.example.com/standard: "true"
platform.example.com/library-version: "v2"
{{- end -}}
