{{/*
Expand the name of the chart.
*/}}
{{- define "chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "chart.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "chart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "chart.labels" -}}
helm.sh/chart: {{ include "chart.chart" . }}
{{ include "chart.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Render volumes section (supports hostPath, configMap and secret sources)
Usage: {{ include "chart.volumes" .Values.someComponent.volumes }}
*/}}
{{- define "chart.volumeMounts" -}}
{{- range $name, $vol := . }}
- mountPath: {{ $vol.mountPath }}
  name: {{ $name }}-vol
  {{- if $vol.readOnly }}
  readOnly: {{ $vol.readOnly }}
  {{- end }}
  {{- if $vol.subPath }}
  subPath: {{ $vol.subPath }}
  {{- end }}
{{- end }}
{{- end }}

{{- define "chart.volumeDefs" -}}
{{- range $name, $vol := . }}
- name: {{ $name }}-vol
  {{- if $vol.secret }}
  secret:
    secretName: {{ $vol.secret }}
  {{- else if $vol.configMap }}
  configMap:
    name: {{ $vol.configMap }}
  {{- else }}
  hostPath:
    path: {{ $vol.hostPath }}
    {{- if $vol.hostPathType }}
    type: {{ $vol.hostPathType }}
    {{- else }}
    type: DirectoryOrCreate
    {{- end }}
  {{- end }}
{{- end }}
{{- end }}
